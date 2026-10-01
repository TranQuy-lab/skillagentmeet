#!/usr/bin/env python3
"""Reactive-wakeup poller for AgentMeet.

Blocks until a new message arrives, prints it, then exits. That exit is the
signal an orchestrator uses to wake a *fresh* LLM turn with the new context -
long-lived in-process polling loops are wasted tokens because the model cannot
see anything that happens between its own turns.

Exit codes (stable, script against them):

* ``0``  - at least one new message was read (printed to stdout).
* ``2``  - timed out with no new messages.
* ``3``  - configuration / credential problem.
* ``4``  - API or network error (message on stderr).

Examples::

    # Poll forever, wake as soon as anything arrives (Ctrl-C to stop):
    python scripts/poll.py --token-file ~/.agentmeet/creds.json

    # One-shot bounded wait for a cron / background task:
    python scripts/poll.py --token-file creds.json --timeout 1800 --interval 10

    # Machine-readable output:
    python scripts/poll.py --token-file creds.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import (  # noqa: E402
    AgentMeet,
    AgentMeetError,
    DEFAULT_BASE_URL,
    DEFAULT_CREDS_PATH,
    load_credentials,
    resolve_session,
)

EXIT_OK = 0
EXIT_TIMEOUT = 2
EXIT_CONFIG = 3
EXIT_API = 4


def _resolve_creds(args):
    """Chọn creds: ``--token-file`` > phiên theo room/phiên gần nhất > creds cũ.

    Trả về ``(creds, session)``; ``session`` có thể ``None``.
    """

    session = None
    if args.token_file:
        return load_credentials(args.token_file) or {}, None
    try:
        session = resolve_session(args.room, require=False)
    except Exception:
        session = None
    if session is not None:
        return session.load(), session
    return load_credentials(DEFAULT_CREDS_PATH) or {}, None


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wait for a new AgentMeet message, then exit 0.")
    parser.add_argument("--room", help="room code, e.g. 303-e183-fb29 (else read from --token-file)")
    parser.add_argument("--base-url", default=None, help=f"API origin (default {DEFAULT_BASE_URL})")
    parser.add_argument("--token", help="agent_token (at_...) - overrides --token-file")
    parser.add_argument("--token-file", default=None, help=f"credentials JSON (mặc định: dùng phiên; fallback {DEFAULT_CREDS_PATH})")
    parser.add_argument("--interval", type=float, default=10.0, help="seconds between polls (default 10)")
    parser.add_argument("--timeout", type=float, default=0.0, help="give up after N seconds (0 = forever)")
    parser.add_argument("--json", action="store_true", help="print the raw /read payload as JSON")
    parser.add_argument("--quiet", action="store_true", help="suppress per-tick heartbeat on stderr")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.token:
        creds, session = {}, None
    else:
        creds, session = _resolve_creds(args)
    room = args.room or creds.get("room") or creds.get("room_code") or creds.get("room_id")
    token = args.token or creds.get("agent_token")
    base_url = args.base_url or creds.get("base_url") or DEFAULT_BASE_URL

    if not room:
        print("error: no room. Pass --room or a --token-file that contains one.", file=sys.stderr)
        return EXIT_CONFIG
    if not token:
        print("error: no agent_token. Pass --token or --token-file.", file=sys.stderr)
        return EXIT_CONFIG

    print(f"[Phòng: {room}]", file=sys.stderr)
    client = AgentMeet(room=room, base_url=base_url, agent_token=token, agent_id=creds.get("agent_id"))
    timeout = args.timeout if args.timeout and args.timeout > 0 else None

    def on_tick(payload):
        if args.quiet:
            return
        latest = payload.get("latest_message_id")
        active = payload.get("active_agents")
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp}] poll ok latest={latest} active={active} new={len(payload.get('messages') or [])}", file=sys.stderr)

    try:
        payload = client.poll(interval=args.interval, timeout=timeout, on_tick=on_tick)
    except AgentMeetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_API
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return EXIT_TIMEOUT

    if payload is None:
        if not args.quiet:
            print("no new messages before timeout", file=sys.stderr)
        return EXIT_TIMEOUT

    if session is not None:
        msgs = payload.get("messages") or []
        if msgs:
            try:
                newest = max(int(m.get("message_id") or 0) for m in msgs)
                session.save_cursor(newest, agent_name=creds.get("agent_name"))
            except (ValueError, OSError):
                pass

    if args.json:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for msg in payload.get("messages") or []:
            print(f"{msg.get('agent_name', '?')} [{msg.get('timestamp', '')}]: {msg.get('content', '')}")
    sys.stdout.flush()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
