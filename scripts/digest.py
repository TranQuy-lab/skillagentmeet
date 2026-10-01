#!/usr/bin/env python3
"""
scripts/digest.py - Team Activity & Tasks Digest Utility

Generates a compact, structured summary of recent room activity without stealing
the destructive /read cursor. Designed for fast human/agent context catch-up.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import AgentMeet, AgentMeetError, load_credentials, DEFAULT_BASE_URL
from agentmeet.protocol import decode


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate team activity and task digest")
    p.add_argument("--room", help="room code")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--token-file", default=r"C:\Users\KBC2\.agentmeet\creds.json")
    p.add_argument("--last", type=int, default=40, help="Analyze last N messages (default: 40)")
    p.add_argument("--since", type=int, default=None, help="Analyze messages with ID > since")
    p.add_argument("--agent", help="Filter analysis to a specific agent name")
    p.add_argument("--tasks-only", action="store_true", help="Show only task lifecycle events")
    p.add_argument("--json", action="store_true", help="Output digest as JSON")
    p.add_argument("--output", "-o", help="Write formatted digest to file")
    return p.parse_args()


def categorize_message(msg: Dict[str, Any]):
    content = str(msg.get("content") or "")
    env = decode(content)
    if env and hasattr(env, "kind"):
        return env.kind, env
    
    # Heuristic detection if envelope decode didn't catch
    lower = content.lower()
    if "[verify]" in lower or "verdict:" in lower:
        return "verify", None
    if "[status]" in lower or "state:" in lower:
        return "status", None
    if "[task]" in lower:
        return "task", None
    if "[heartbeat]" in lower or "heartbeat posted" in lower:
        return "heartbeat", None
    return "chat", None


def extract_mentions(text: str) -> List[str]:
    return re.findall(r"@([A-Za-z0-9_.-]+(?:\s+[A-Za-z0-9_.-]+)?)", text)


def build_digest(messages: List[Dict[str, Any]], target_agent: Optional[str] = None) -> Dict[str, Any]:
    if not messages:
        return {
            "total_messages": 0,
            "agents": {},
            "tasks": [],
            "mentions": [],
            "latest_id": None,
            "earliest_id": None
        }

    if target_agent:
        messages = [m for m in messages if m.get("agent_name", "").lower() == target_agent.lower()]

    agent_counts = Counter()
    agent_kinds = defaultdict(lambda: Counter())
    task_events = []
    mentions_list = []

    for m in messages:
        sender = m.get("agent_name") or "unknown"
        msg_id = m.get("message_id")
        content = m.get("content", "")
        ts = m.get("timestamp", "")
        kind, env = categorize_message(m)

        agent_counts[sender] += 1
        agent_kinds[sender][kind] += 1

        if kind in ("task", "claim", "status", "review", "verify", "dissent") or env:
            data = getattr(env, "data", {}) if env else {}
            task_events.append({
                "id": msg_id,
                "ts": ts,
                "by": sender,
                "kind": kind,
                "task": data.get("task") or data.get("task_id"),
                "state": data.get("state") or data.get("status"),
                "verdict": data.get("verdict"),
                "note": data.get("note") or data.get("proof") or (content[:80] + "..." if len(content) > 80 else content)
            })

        found_mentions = extract_mentions(content)
        if found_mentions:
            mentions_list.append({
                "id": msg_id,
                "from": sender,
                "mentions": found_mentions,
                "snippet": content[:100].replace("\n", " ")
            })

    return {
        "total_messages": len(messages),
        "earliest_id": messages[0].get("message_id") if messages else None,
        "latest_id": messages[-1].get("message_id") if messages else None,
        "agents": {
            agent: {
                "total": count,
                "kinds": dict(agent_kinds[agent])
            }
            for agent, count in agent_counts.most_common()
        },
        "tasks": task_events,
        "mentions": mentions_list[-10:]  # last 10 mentions
    }


def format_markdown(digest: Dict[str, Any], tasks_only: bool = False) -> str:
    lines = []
    lines.append(f"# 📊 Team Activity Digest (Msgs #{digest.get('earliest_id')} - #{digest.get('latest_id')})")
    lines.append(f"**Total Analyzed**: {digest.get('total_messages')} messages | **Active Agents**: {len(digest.get('agents', {}))}\n")

    if not tasks_only:
        lines.append("## 👥 Agent Participation")
        lines.append("| Agent | Total Msgs | Chat | Task/Status | Verify | Heartbeat |")
        lines.append("|---|---|---|---|---|---|")
        for agent, stats in digest.get("agents", {}).items():
            k = stats.get("kinds", {})
            task_stat = k.get("task", 0) + k.get("status", 0) + k.get("claim", 0) + k.get("review", 0)
            lines.append(
                f"| **{agent}** | {stats.get('total')} | {k.get('chat', 0)} | {task_stat} | {k.get('verify', 0)} | {k.get('heartbeat', 0)} |"
            )
        lines.append("")

    lines.append("## 📋 Task & Verification Events")
    tasks = digest.get("tasks", [])
    if not tasks:
        lines.append("_No task events in this range._\n")
    else:
        lines.append("| Msg | By | Kind | Task | State / Verdict | Details |")
        lines.append("|---|---|---|---|---|---|")
        for t in tasks:
            task_name = t.get("task") or "-"
            state_verdict = t.get("state") or t.get("verdict") or "-"
            note = (t.get("note") or "").replace("\n", " ")
            if len(note) > 60:
                note = note[:57] + "..."
            lines.append(f"| #{t.get('id')} | {t.get('by')} | `{t.get('kind')}` | **{task_name}** | `{state_verdict}` | {note} |")
        lines.append("")

    if not tasks_only:
        lines.append("## 🔔 Recent Mentions & Directives")
        mentions = digest.get("mentions", [])
        if not mentions:
            lines.append("_No recent mentions._\n")
        else:
            for m in mentions:
                targets = ", ".join(f"@{t}" for t in m.get("mentions", []))
                lines.append(f"- **#{m.get('id')} {m.get('from')}** → {targets}: _{m.get('snippet')}_")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    creds = load_credentials(args.token_file) if args.token_file else {}
    room = args.room or creds.get("room") or creds.get("room_code")
    base_url = args.base_url or creds.get("base_url") or DEFAULT_BASE_URL
    token = creds.get("agent_token")

    if not room:
        print("error: missing room code (--room or --token-file)", file=sys.stderr)
        return 1

    client = AgentMeet(room=room, base_url=base_url, agent_token=token)

    try:
        if args.since is not None:
            # Need messages after since ID
            probe = client.transcript(limit=1)
            total = probe.get("total_messages", 0)
            # Fetch recent chunk or all
            offset = max(0, total - 200)
            data = client.transcript(limit=100, offset=offset)
            messages = data.get("messages", [])
            if data.get("has_more"):
                more = client.transcript(limit=100, offset=offset + 100)
                messages.extend(more.get("messages", []))
            messages = [m for m in messages if (m.get("message_id") or 0) > args.since]
        elif args.last:
            probe = client.transcript(limit=1)
            total = probe.get("total_messages", 0)
            offset = max(0, total - args.last)
            data = client.transcript(limit=args.last, offset=offset)
            messages = data.get("messages", [])
        else:
            data = client.transcript(limit=50)
            messages = data.get("messages", [])
    except AgentMeetError as e:
        print(f"error fetching transcript: {e}", file=sys.stderr)
        return 2

    digest = build_digest(messages, target_agent=args.agent)

    if args.json:
        output_str = json.dumps(digest, ensure_ascii=False, indent=2)
    else:
        output_str = format_markdown(digest, tasks_only=args.tasks_only)

    if args.output:
        Path(args.output).write_text(output_str, encoding="utf-8")
        print(f"Digest written to {args.output}")
    else:
        print(output_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
