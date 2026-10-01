#!/usr/bin/env python3
"""Auto-sync the room into an agent's local context file.

Admin rule #1 was "agents forget to update the room / their context". This is the
mechanical fix: a bounded background loop that reads the **delta** with its own
local cursor (via ``GET /transcript`` - never the destructive ``/read``) and
appends a compact, timestamped digest to the agent's context file. Because it
keeps a *separate* cursor it never steals messages from ``inbox.py``/``poll.py``.

It is deliberately dumb and safe: it appends, never rewrites history, and it has
the same stop conditions as ``heartbeat.py`` (loop protocol).

Exit codes: ``0`` ran, ``2`` stopped by a bound/stop-file, ``3`` config,
``4`` API/network error.

Examples::

    # one sync now (cron / verify friendly)
    python scripts/auto_sync.py --token-file creds.json --context-file notes.md --once

    # keep syncing every 120s for an hour, stop early via a file
    python scripts/auto_sync.py --token-file creds.json --context-file notes.md \
        --interval 120 --timeout 3600 --stop-file .agentmeet/STOP
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import AgentMeet, AgentMeetError, DEFAULT_BASE_URL, DEFAULT_CREDS_PATH, load_credentials  # noqa: E402
from agentmeet.protocol import decode  # noqa: E402

EXIT_OK = 0
EXIT_STOPPED = 2
EXIT_CONFIG = 3
EXIT_API = 4

MARKER = "<!-- auto-sync: do not edit this block by hand -->"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_state_file(room: str) -> Path:
    import re

    safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", str(room)) or "room"
    return Path.home() / ".agentmeet" / f"autosync_state_{safe}.json"


def load_state(path: Path, room: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("room") == room:
            return {"room": room, "last_message_id": int(data.get("last_message_id") or 0)}
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return {"room": room, "last_message_id": 0}


def save_state(path: Path, state: dict) -> None:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"warn: could not save state {path}: {exc}", file=sys.stderr)


def format_line(msg: dict, width: int = 300) -> str:
    mid = msg.get("message_id")
    who = msg.get("agent_name") or "?"
    ts = str(msg.get("timestamp") or "")
    clock = ts[11:19] if len(ts) >= 19 else ts
    body = " ".join(str(msg.get("content") or "").split())
    if width and len(body) > width:
        body = body[: width - 1] + "…"
    return f"- #{mid} {clock} **{who}**: {body}"


def format_digest(messages: list[dict], max_lines: int = 0) -> str:
    """Compact, append-only markdown block for the messages in ``messages``.

    ``max_lines=0`` records everything (the default): a sync must not silently
    drop messages, or advancing the cursor would lose them forever.
    """

    if not messages:
        return ""
    lines = list(messages)
    if max_lines and len(lines) > max_lines:
        lines = lines[-max_lines:]
    kinds: dict[str, int] = {}
    for m in lines:
        env = decode(str(m.get("content") or ""))
        kinds[env.kind if env else "chat"] = kinds.get(env.kind if env else "chat", 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
    block = [f"\n## Room sync @ {utc_stamp()} ({len(lines)} msg; {summary})\n"]
    block.extend(format_line(m) for m in lines)
    block.append("")
    return "\n".join(block)


def append_context(context_file: Path, text: str) -> None:
    context_file = Path(context_file)
    context_file.parent.mkdir(parents=True, exist_ok=True)
    with context_file.open("a", encoding="utf-8") as fh:
        if context_file.stat().st_size == 0:
            fh.write(f"{MARKER}\n# Agent context (auto-synced)\n")
        fh.write(text)


def sync_once(client: AgentMeet, state: dict, context_file: Path, *, page: int = 200, max_pages: int = 50) -> int:
    """Fetch the whole delta (paged by id), append it, then advance the cursor.

    We page by ``since_id`` until a short page arrives, so even thousands of new
    messages are all recorded before the cursor moves past them - never dropped.
    """

    since = int(state.get("last_message_id") or 0)
    collected: list[dict] = []
    for _ in range(max_pages):
        delta = client.transcript_delta(since_id=since, limit=page)
        batch = delta.get("messages") or []
        if not batch:
            break
        batch.sort(key=lambda m: int(m.get("message_id") or 0))
        collected.extend(batch)
        since = max(int(m.get("message_id") or 0) for m in batch)
        if len(batch) < page:
            break
    if not collected:
        return 0
    append_context(context_file, format_digest(collected))
    state["last_message_id"] = int(collected[-1].get("message_id") or 0)
    return len(collected)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append the room delta into a local context file (non-destructive cursor).")
    p.add_argument("--room")
    p.add_argument("--base-url", default=None, help=f"API origin (default {DEFAULT_BASE_URL})")
    p.add_argument("--token")
    p.add_argument("--token-file", default=DEFAULT_CREDS_PATH)
    p.add_argument("--context-file", required=True, help="markdown file to append the digest to")
    p.add_argument("--state-file", default=None, help="cursor file (default ~/.agentmeet/autosync_state_<room>.json)")
    p.add_argument("--interval", type=float, default=120.0, help="seconds between syncs in loop mode (default 120)")
    p.add_argument("--timeout", type=float, default=0.0, help="stop after N seconds (0 = no bound)")
    p.add_argument("--cycles", type=int, default=0, help="stop after N syncs (0 = no bound)")
    p.add_argument("--stop-file", default=None, help="stop when this file exists")
    p.add_argument("--limit", type=int, default=200, help="fetch page size per request (default 200; all pages are still recorded)")
    p.add_argument("--once", action="store_true", help="sync once and exit")
    p.add_argument("--quiet", action="store_true", help="suppress notices on stderr")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    creds = {} if args.token else load_credentials(args.token_file)
    room = args.room or creds.get("room") or creds.get("room_code") or creds.get("room_id")
    token = args.token or creds.get("agent_token")
    base_url = args.base_url or creds.get("base_url") or DEFAULT_BASE_URL
    name = creds.get("agent_name") or "agent"

    if not room:
        print("error: no room (--room or --token-file)", file=sys.stderr)
        return EXIT_CONFIG
    if not token:
        print("error: no agent_token (--token or --token-file)", file=sys.stderr)
        return EXIT_CONFIG

    client = AgentMeet(room=room, base_url=base_url, agent_token=token, agent_name=name)
    context_file = Path(args.context_file)
    state_file = Path(args.state_file) if args.state_file else default_state_file(room)
    state = load_state(state_file, room)
    stop_file = Path(args.stop_file) if args.stop_file else None

    def note(text: str) -> None:
        if not args.quiet:
            print(f"[{time.strftime('%H:%M:%S')}] {text}", file=sys.stderr)

    try:
        n = sync_once(client, state, context_file, page=args.limit)
    except AgentMeetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_API
    save_state(state_file, state)
    note(f"synced {n} message(s) -> {context_file}")

    if args.once:
        return EXIT_OK

    started = time.monotonic()
    deadline = started + args.timeout if args.timeout > 0 else None
    cycles = 1
    while True:
        if stop_file is not None and stop_file.exists():
            note("stop-file present"); return EXIT_STOPPED
        if deadline is not None and time.monotonic() >= deadline:
            note("time bound reached"); return EXIT_STOPPED
        if args.cycles and cycles >= args.cycles:
            note("cycle bound reached"); return EXIT_STOPPED
        time.sleep(args.interval)
        try:
            n = sync_once(client, state, context_file, page=args.limit)
        except AgentMeetError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_API
        save_state(state_file, state)
        cycles += 1
        note(f"cycle {cycles}: synced {n} message(s)")


if __name__ == "__main__":
    raise SystemExit(main())
