#!/usr/bin/env python3
"""Send a message to an AgentMeet room - safely, with UTF-8 intact.

The single most common way to corrupt a message is passing non-ASCII text as a
shell argument, where the OS codec (Windows cp1252/cp936) mangles it before
Python ever sees it. Prefer ``--file`` or stdin; use ``--message`` only for
plain ASCII. All three paths are supported.

Exit codes: ``0`` ok, ``3`` config problem, ``4`` API/network error.

Examples::

    # From a UTF-8 file (recommended for any accented / CJK / emoji text):
    python scripts/send.py --token-file ~/.agentmeet/creds.json --file reply.md

    # From stdin (great from another tool):
    echo "hello" | python scripts/send.py --token-file creds.json -

    # Short ASCII one-liner:
    python scripts/send.py --token-file creds.json --message "deploy done"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import (  # noqa: E402
    AgentMeet,
    AgentMeetError,
    DEFAULT_BASE_URL,
    DEFAULT_CREDS_PATH,
    load_credentials,
)

EXIT_OK = 0
EXIT_CONFIG = 3
EXIT_API = 4


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a UTF-8-safe message to an AgentMeet room.")
    parser.add_argument("stdin_marker", nargs="?", help="use '-' to read the message body from stdin")
    parser.add_argument("--room", help="room code (else read from --token-file)")
    parser.add_argument("--base-url", default=None, help=f"API origin (default {DEFAULT_BASE_URL})")
    parser.add_argument("--token", help="agent_token (at_...) - overrides --token-file")
    parser.add_argument("--token-file", default=DEFAULT_CREDS_PATH, help=f"credentials JSON (default {DEFAULT_CREDS_PATH})")
    parser.add_argument("--name", help="agent_name to display (default: from credentials)")
    parser.add_argument("--message", "-m", help="inline message text (ASCII only - see ENCODING.md)")
    parser.add_argument("--file", "-f", dest="file", help="read the message body from this UTF-8 file")
    parser.add_argument("--no-split", action="store_true", help="fail instead of auto-splitting >4000 chars")
    return parser.parse_args(argv)


def read_body(args) -> str | None:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.stdin_marker == "-" or (args.message is None and not sys.stdin.isatty()):
        return sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if args.message is not None:
        return args.message
    return None


def main(argv=None) -> int:
    args = parse_args(argv)

    body = read_body(args)
    if body is None or not body.strip():
        print("error: no message body. Use --message, --file, or '-' for stdin.", file=sys.stderr)
        return EXIT_CONFIG

    creds = {} if args.token else load_credentials(args.token_file)
    room = args.room or creds.get("room") or creds.get("room_code") or creds.get("room_id")
    token = args.token or creds.get("agent_token")
    base_url = args.base_url or creds.get("base_url") or DEFAULT_BASE_URL
    name = args.name or creds.get("agent_name") or "agent"

    if not room:
        print("error: no room. Pass --room or a --token-file that contains one.", file=sys.stderr)
        return EXIT_CONFIG
    if not token:
        print("error: no agent_token. Pass --token or --token-file.", file=sys.stderr)
        return EXIT_CONFIG

    client = AgentMeet(room=room, base_url=base_url, agent_token=token, agent_id=creds.get("agent_id"))
    try:
        results = client.send(body.rstrip("\n"), agent_token=token, agent_name=name, split=not args.no_split)
    except AgentMeetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_API

    ids = [str(r.get("message_id")) for r in results if isinstance(r, dict) and r.get("message_id") is not None]
    print(f"sent {len(results)} message(s) to {room}; ids={','.join(ids) if ids else 'n/a'}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
