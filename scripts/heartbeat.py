#!/usr/bin/env python3
"""Keep an agent alive *and* visible: bounded loop + automatic heartbeats.

Two real multi-agent failure modes this fixes:

1. **Silent agents.** An agent works for twenty minutes and posts nothing, so
   the team assumes it died (or finished). ``heartbeat`` posts a cheap liveness
   line whenever the agent has been quiet longer than ``--idle``.
2. **Agents that stop too early / never stop.** The loop only ends on an
   explicit stop condition (new message, ``--cycles``, ``--timeout``,
   ``--stop-file``), never on "I feel done".

It is still a *reactive* poller in spirit: the moment a new message arrives it
prints it and exits ``0`` so the orchestrator can wake a fresh LLM turn. Between
messages it beats every ``--idle`` seconds and keeps looping until a bound is
hit. See ``docs/OPERATIONS.md`` sections 1, 2 and 7.

Exit codes: ``0`` new message (printed), ``2`` stopped by a bound/stop-file
without a new message, ``3`` config problem, ``4`` API/network error.

Examples::

    # Loop for an hour, beat every 5 min, wake immediately on any message:
    python scripts/heartbeat.py --token-file creds.json --timeout 3600 --idle 300 \
        --status "building T1a2b3" --next "run tests"

    # Stop when the lead says so (creates the file) or after 20 cycles:
    python scripts/heartbeat.py --token-file creds.json --cycles 20 \
        --stop-file .agentmeet/STOP

    # Post exactly one heartbeat now and exit (no looping):
    python scripts/heartbeat.py --token-file creds.json --once --status "resuming"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import AgentMeet, AgentMeetError, DEFAULT_BASE_URL, DEFAULT_CREDS_PATH, encode, load_credentials  # noqa: E402

EXIT_OK = 0
EXIT_STOPPED = 2
EXIT_CONFIG = 3
EXIT_API = 4


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded agent loop with automatic heartbeats.")
    p.add_argument("--room")
    p.add_argument("--base-url", default=None, help=f"API origin (default {DEFAULT_BASE_URL})")
    p.add_argument("--token")
    p.add_argument("--token-file", default=DEFAULT_CREDS_PATH)
    p.add_argument("--name", help="agent_name (default: from credentials)")
    p.add_argument("--interval", type=float, default=10.0, help="seconds between polls (default 10)")
    p.add_argument("--idle", type=float, default=300.0, help="post a heartbeat after this many quiet seconds (default 300)")
    p.add_argument("--timeout", type=float, default=0.0, help="stop after N seconds total (0 = no time bound)")
    p.add_argument("--cycles", type=int, default=0, help="stop after N poll cycles (0 = no cycle bound)")
    p.add_argument("--stop-file", default=None, help="stop when this file exists (lead/consensus stop signal)")
    p.add_argument("--stop-on", default=None, help="stop when a new message matches this regex")
    p.add_argument("--status", default="", help="free-text status for the heartbeat")
    p.add_argument("--task", default=None, help="current task id for the heartbeat envelope")
    p.add_argument("--state", default=None, help="current task state (doing/review/...)")
    p.add_argument("--next", dest="next_action", default=None, help="what you will do next")
    p.add_argument("--once", action="store_true", help="post a single heartbeat and exit (skip polling)")
    p.add_argument("--no-heartbeat", action="store_true", help="poll only; never post a heartbeat")
    p.add_argument("--json", action="store_true", help="print new messages as JSON")
    p.add_argument("--quiet", action="store_true", help="suppress heartbeat/poll notices on stderr")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    creds = {} if args.token else load_credentials(args.token_file)
    room = args.room or creds.get("room") or creds.get("room_code") or creds.get("room_id")
    token = args.token or creds.get("agent_token")
    base_url = args.base_url or creds.get("base_url") or DEFAULT_BASE_URL
    name = args.name or creds.get("agent_name") or "agent"

    if not room:
        print("error: no room (--room or --token-file)", file=sys.stderr)
        return EXIT_CONFIG
    if not token:
        print("error: no agent_token (--token or --token-file)", file=sys.stderr)
        return EXIT_CONFIG

    client = AgentMeet(room=room, base_url=base_url, agent_token=token, agent_name=name)
    stop_file = Path(args.stop_file) if args.stop_file else None
    stop_re = re.compile(args.stop_on) if args.stop_on else None

    def post_heartbeat(note: str = "") -> bool:
        data = {"by": name, "note": note or args.status, "next": args.next_action}
        if args.task:
            data["task"] = args.task
        if args.state:
            data["state"] = args.state
        data = {k: v for k, v in data.items() if v is not None}
        try:
            client.send(encode("heartbeat", data), agent_token=token, agent_name=name)
        except AgentMeetError as exc:
            print(f"warn: heartbeat failed: {exc}", file=sys.stderr)
            return False
        if not args.quiet:
            stamp = time.strftime("%H:%M:%S")
            print(f"[{stamp}] heartbeat posted: {args.status or note or '(alive)'}", file=sys.stderr)
        return True

    if args.once:
        post_heartbeat("once")
        return EXIT_OK

    started = time.monotonic()
    last_beat = started
    deadline = started + args.timeout if args.timeout > 0 else None
    cycle = 0

    while True:
        cycle += 1

        # 1. stop conditions that do not need a request
        if stop_file is not None and stop_file.exists():
            if not args.quiet:
                print(f"[stop] stop-file present: {stop_file}", file=sys.stderr)
            return EXIT_STOPPED
        if deadline is not None and time.monotonic() >= deadline:
            if not args.quiet:
                print("[stop] time bound reached", file=sys.stderr)
            return EXIT_STOPPED
        if args.cycles and cycle > args.cycles:
            if not args.quiet:
                print("[stop] cycle bound reached", file=sys.stderr)
            return EXIT_STOPPED

        # 2. read new messages (destructive /read cursor; this is the main reader)
        try:
            payload = client.read(agent_token=token)
        except AgentMeetError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_API

        messages = payload.get("messages") or []
        if messages:
            if args.json:
                json.dump(messages, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
            else:
                for msg in messages:
                    print(f"{msg.get('agent_name', '?')} [{msg.get('timestamp', '')}]: {msg.get('content', '')}")
            sys.stdout.flush()
            if stop_re is not None and any(stop_re.search(str(m.get("content") or "")) for m in messages):
                if not args.quiet:
                    print("[stop] stop-on matched", file=sys.stderr)
                return EXIT_STOPPED
            return EXIT_OK

        # 3. nothing new: beat if we have been quiet too long
        now = time.monotonic()
        if not args.no_heartbeat and (now - last_beat) >= args.idle:
            post_heartbeat()
            last_beat = now

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
