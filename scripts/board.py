#!/usr/bin/env python3
"""A shared task board for a team of agents, stored in the AgentMeet room.

Parallel coding fails when two agents do not know who owns what. This CLI
records tasks, claims, status changes, reviews, blockers and objections as
*structured* messages in the room, then reconstructs the current board by
folding the transcript.

It reads state from ``GET /transcript`` (paginated, non-destructive), never
from ``/read`` - so using the board does **not** steal messages from a poller
that is waiting on the same token.

Examples::

    # Lead/any agent creates tasks:
    python scripts/board.py --token-file creds.json task "Bound CTE depth" --files order.go,user_proxy.go
    python scripts/board.py --token-file creds.json task "Add idempotency" --files order.go

    # A worker claims and reports:
    python scripts/board.py --token-file creds.json claim T1a2b3
    python scripts/board.py --token-file creds.json status T1a2b3 doing --note "phase 1"
    python scripts/board.py --token-file creds.json review T1a2b3 pass --note "looks safe"

    # A member objects (always allowed, see docs/LEADERSHIP.md):
    python scripts/board.py --token-file creds.json dissent T1a2b3 --reason "touches money path"

    # An INDEPENDENT verifier reproduces the result before "done" (docs/OPERATIONS.md):
    python scripts/board.py --token-file creds.json verify T1a2b3 pass --note "re-ran tests, 42 passed"

    # See the whole board:
    python scripts/board.py --token-file creds.json list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import (  # noqa: E402
    AgentMeet,
    AgentMeetError,
    DEFAULT_BASE_URL,
    DEFAULT_CREDS_PATH,
    build_board,
    board_summary,
    encode,
    load_credentials,
    new_id,
)
from agentmeet.protocol import CLAIMED, DOING, REVIEW, STATES  # noqa: E402

EXIT_OK = 0
EXIT_CONFIG = 3
EXIT_API = 4


def _client(args):
    creds_file = getattr(args, "token_file", None) or DEFAULT_CREDS_PATH
    creds = {} if getattr(args, "token", None) else load_credentials(creds_file)
    room = getattr(args, "room", None) or creds.get("room") or creds.get("room_code") or creds.get("room_id")
    token = getattr(args, "token", None) or creds.get("agent_token")
    base_url = getattr(args, "base_url", None) or creds.get("base_url") or DEFAULT_BASE_URL
    name = getattr(args, "as_name", None) or creds.get("agent_name") or "agent"
    if not room:
        print("error: no room (--room or --token-file)", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    if not token:
        print("error: no agent_token (--token or --token-file)", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    return AgentMeet(room=room, base_url=base_url, agent_token=token, agent_name=name), name


def _split_csv(value):
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def parse_args(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--room", default=None, help="AgentMeet room code")
    common.add_argument("--base-url", default=None, help=f"API origin (default {DEFAULT_BASE_URL})")
    common.add_argument("--token", default=None, help="agent_token (at_...)")
    common.add_argument("--token-file", default=None, help=f"credentials JSON (default {DEFAULT_CREDS_PATH})")
    common.add_argument("--as", dest="as_name", default=None, help="agent name to post as (default: from creds)")

    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument("--room", default=argparse.SUPPRESS)
    sub_common.add_argument("--base-url", default=argparse.SUPPRESS)
    sub_common.add_argument("--token", default=argparse.SUPPRESS)
    sub_common.add_argument("--token-file", default=argparse.SUPPRESS)
    sub_common.add_argument("--as", dest="as_name", default=argparse.SUPPRESS)

    p = argparse.ArgumentParser(description="Shared AgentMeet task board.", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("task", parents=[sub_common], help="create a task")
    t.add_argument("title")
    t.add_argument("--id", dest="task_id", help="explicit task id (default: generated)")
    t.add_argument("--files", help="comma-separated file paths this task touches")
    t.add_argument("--owner")
    t.add_argument("--reviewers", help="comma-separated reviewer agent names")
    t.add_argument("--note")

    c = sub.add_parser("claim", parents=[sub_common], help="claim a task")
    c.add_argument("task_id")

    s = sub.add_parser("status", parents=[sub_common], help="set task state")
    s.add_argument("task_id")
    s.add_argument("state", choices=list(STATES))
    s.add_argument("--note")

    r = sub.add_parser("review", parents=[sub_common], help="post a review verdict")
    r.add_argument("task_id")
    r.add_argument("verdict", choices=["pass", "fail"])
    r.add_argument("--note")

    b = sub.add_parser("block", parents=[sub_common], help="mark a task blocked")
    b.add_argument("task_id")
    b.add_argument("--reason", required=True)

    d = sub.add_parser("dissent", parents=[sub_common], help="record an objection (member right)")
    d.add_argument("task_id")
    d.add_argument("--reason", required=True)

    cd = sub.add_parser("clear-dissent", parents=[sub_common], help="clear objection on a task after resolution")
    cd.add_argument("task_id")
    cd.add_argument("--reason", default="", help="reason/resolution note")

    v = sub.add_parser("verify", parents=[sub_common], help="independent verification; required before a task is done")
    v.add_argument("task_id")
    v.add_argument("verdict", choices=["pass", "fail"])
    v.add_argument("--note")

    li = sub.add_parser("list", parents=[sub_common], help="print the current board")
    li.add_argument("--json", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    client, name = _client(args)

    if args.cmd == "list":
        try:
            room = client.transcript_all(page_size=100)
        except AgentMeetError as exc:
            print(f"[room: {client.room}] error: {exc}", file=sys.stderr)
            return EXIT_API
        board = build_board(room.get("messages") or [])
        if args.json:
            json.dump({k: v.as_dict() for k, v in board.items()}, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"[room: {client.room}]")
            print(board_summary(board))
        return EXIT_OK

    try:
        if args.cmd == "task":
            tid = args.task_id or new_id()
            text = encode("task", {
                "task": tid, "title": args.title, "files": _split_csv(args.files),
                "owner": args.owner, "reviewers": _split_csv(args.reviewers),
                "note": args.note, "by": name,
            })
        elif args.cmd == "claim":
            text = encode("claim", {"task": args.task_id, "by": name})
        elif args.cmd == "status":
            text = encode("status", {"task": args.task_id, "state": args.state, "note": args.note, "by": name})
        elif args.cmd == "review":
            text = encode("review", {"task": args.task_id, "verdict": args.verdict, "note": args.note, "by": name})
        elif args.cmd == "block":
            text = encode("block", {"task": args.task_id, "reason": args.reason, "by": name})
        elif args.cmd == "dissent":
            text = encode("dissent", {"task": args.task_id, "reason": args.reason, "by": name})
        elif args.cmd == "clear-dissent":
            text = encode("clear_dissent", {"task": args.task_id, "reason": args.reason, "by": name})
        elif args.cmd == "verify":
            # Guard against self-verification: an author cannot verify their own task
            try:
                room_data = client.transcript_all(page_size=100)
                curr_board = build_board(room_data.get("messages") or [])
                if args.task_id in curr_board:
                    task_owner = curr_board[args.task_id].owner
                    if task_owner and (name == task_owner or name.lower() == str(task_owner).lower()):
                        print(f"[room: {client.room}] error: author cannot self-verify task {args.task_id} (owner: {task_owner})", file=sys.stderr)
                        return EXIT_CONFIG
            except AgentMeetError:
                pass
            text = encode("verify", {"task": args.task_id, "verdict": args.verdict, "note": args.note, "by": name})
        else:  # pragma: no cover - argparse enforces the set
            print(f"[room: {client.room}] error: unknown command", file=sys.stderr)
            return EXIT_CONFIG
        client.send(text, agent_token=client.agent_token, agent_name=name)
    except AgentMeetError as exc:
        print(f"[room: {client.room}] error: {exc}", file=sys.stderr)
        return EXIT_API

    if args.cmd == "task":
        print(f"[room: {client.room}] created task {tid}")
    else:
        print(f"[room: {client.room}] {args.cmd} {args.task_id} posted as {name}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
