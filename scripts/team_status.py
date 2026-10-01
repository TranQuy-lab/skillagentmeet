#!/usr/bin/env python3
"""team_status.py - Quick team status dashboard for AgentMeet.

Shows room info, active agents, recent activity summary, and message stats.
Designed as a lightweight "dashboard" that doesn't consume much context.

Usage:
    python team_status.py              # Full dashboard
    python team_status.py --compact    # One-line per agent
    python team_status.py --json       # JSON output
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from agentmeet import AgentMeet


def load_creds(token_file=None):
    creds_path = token_file or os.environ.get("AGENTMEET_CREDS", r"/home/noble-tran/agent-meet_skill\agent_creds.json")
    with open(creds_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="AgentMeet team status dashboard")
    parser.add_argument("--compact", action="store_true", help="Compact output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--token-file", default=None, help="Path to credentials file")
    args = parser.parse_args()

    creds = load_creds(args.token_file)
    room = creds.get("room") or creds.get("room_code") or creds.get("room_id")
    m = AgentMeet(room=room)

    # Get room status
    try:
        status = m.status()
    except Exception as e:
        print(f"ERROR getting status: {e}", file=sys.stderr)
        sys.exit(1)

    # Get recent messages for activity stats (fetch LATEST 100, not first 100)
    try:
        # First get total count
        status_data = m.transcript(limit=1)
        total_msgs = status_data.get("total_messages", 0)
        # Calculate offset to get last 100 messages
        offset = max(0, total_msgs - 100)
        transcript = m.transcript(limit=100, offset=offset)
        messages = transcript.get("messages", [])
    except Exception:
        messages = []
        total_msgs = 0

    # Build stats
    total_msgs = transcript.get("total_messages", len(messages))
    sender_counts = Counter(msg.get("agent_name", "?") for msg in messages)
    
    # Recent activity (last 10 messages)
    recent = messages[-10:] if messages else []
    
    dashboard = {
        "room": creds["room"],
        "total_messages": total_msgs,
        "active_agents": len(sender_counts),
        "agents": [],
        "recent_activity": [],
    }

    # Build agent list from messages (more reliable than status API)
    all_senders = sorted(sender_counts.keys())
    for name in all_senders:
        dashboard["agents"].append({
            "name": name,
            "id": "?",
            "recent_msgs": sender_counts.get(name, 0),
        })

    for msg in recent:
        dashboard["recent_activity"].append({
            "id": msg.get("message_id"),
            "sender": msg.get("agent_name", "?"),
            "time": msg.get("timestamp", "")[:19],
            "preview": msg.get("content", "")[:80].replace("\n", " "),
        })

    if args.json:
        print(json.dumps(dashboard, ensure_ascii=False, indent=2))
    elif args.compact:
        print(f"Room: {dashboard['room']} | Msgs: {total_msgs} | Agents: {dashboard['active_agents']}")
        for a in dashboard["agents"]:
            print(f"  {a['name']}: {a['recent_msgs']} msgs (recent)")
    else:
        print("=" * 60)
        print(f"  AGENTMEET TEAM DASHBOARD")
        print(f"  Room: {dashboard['room']}")
        print(f"  Total Messages: {total_msgs}")
        print(f"  Active Agents: {dashboard['active_agents']}")
        print("=" * 60)
        
        print("\n📋 AGENTS:")
        for a in dashboard["agents"]:
            print(f"  • {a['name']} (id: {a['id'][:12]}...) — {a['recent_msgs']} msgs in last 100")
        
        print(f"\n📨 RECENT ACTIVITY (last {len(recent)}):")
        for act in dashboard["recent_activity"]:
            print(f"  #{act['id']:>4} [{act['time']}] {act['sender']}: {act['preview']}...")
        
        print("=" * 60)


if __name__ == "__main__":
    main()
