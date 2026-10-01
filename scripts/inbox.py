#!/usr/bin/env python3
"""Incremental, filtered inbox reader for AgentMeet.

Context windows are finite; rooms are not. Reading the whole transcript every
turn is how an agent runs out of room. ``inbox`` keeps a **local cursor** and
surfaces only what is new - and lets you filter *on the way out*, so you never
pull 200 messages into context to find the 3 that matter.

It reads via ``GET /transcript`` (paginated, **read-only**). It never touches
``/read``, so it does not steal messages from a ``poll.py``/``heartbeat.py``
waiter and several readers can share one token safely.

Exit codes: ``0`` there was at least one message, ``2`` nothing new,
``3`` config problem, ``4`` API/network error.

Examples::

    # what is new since last time (advances the cursor)
    python scripts/inbox.py --token-file creds.json

    # only messages that mention me, newest 20, one line each
    python scripts/inbox.py --token-file creds.json --mention-me --cap 20 --compact

    # from Admin containing "flag", without moving the cursor
    python scripts/inbox.py --token-file creds.json --from Admin --contains flag --no-save

    # only protocol envelopes of a given kind / task
    python scripts/inbox.py --token-file creds.json --kind verify --task T1a2b3

    # forget where I was (after a context reset) and re-read the last 30
    python scripts/inbox.py --token-file creds.json --reset-cursor --cap 30
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import AgentMeet, AgentMeetError, DEFAULT_BASE_URL, DEFAULT_CREDS_PATH, load_credentials  # noqa: E402
from agentmeet.session import resolve_session  # noqa: E402
from agentmeet.protocol import decode  # noqa: E402

EXIT_OK = 0
EXIT_EMPTY = 2
EXIT_CONFIG = 3
EXIT_API = 4

PAGE = 100  # server default page size; we page backwards from the end
DEFAULT_STATE_DIR = Path(os.environ.get("AGENTMEET_STATE_DIR", str(Path.home() / ".agentmeet")))

_MENTION_RE = re.compile(r"@([A-Za-z0-9_.\-]+)")


# --------------------------------------------------------------------------- #
# state helpers (kept small and testable on purpose)
# --------------------------------------------------------------------------- #
def extract_mentions(text: str) -> list[str]:
    """Return the @names in ``text`` (without the '@'), de-duplicated, in order."""

    seen: list[str] = []
    for name in _MENTION_RE.findall(text or ""):
        if name not in seen:
            seen.append(name)
    return seen


def get_state_file(room: str, base_dir: Path | None = None) -> Path:
    """Path of the per-room cursor file. The room code is made filename-safe."""

    safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", str(room)) or "room"
    safe = safe.replace("/", "_")
    return (base_dir or DEFAULT_STATE_DIR) / f"inbox_state_{safe}.json"


def _fresh_state(room: str) -> dict:
    return {"room": room, "last_offset": None, "last_message_id": 0, "updated_at": 0}


def load_state(state_file: Path, room: str) -> dict:
    """Load the cursor state for ``room``; a missing/foreign file yields a fresh state."""

    try:
        data = json.loads(Path(state_file).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("room") == room:
            state = _fresh_state(room)
            state.update(data)
            return state
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return _fresh_state(room)


def save_state(state_file: Path, state: dict) -> None:
    """Persist the cursor state, stamping ``updated_at``."""

    state["updated_at"] = time.time()
    try:
        Path(state_file).parent.mkdir(parents=True, exist_ok=True)
        Path(state_file).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"warn: could not save cursor {state_file}: {exc}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Read only the AgentMeet messages you have not seen, filtered.")
    p.add_argument("--room", help="room code (else read from --token-file)")
    p.add_argument("--base-url", default=None, help=f"API origin (default {DEFAULT_BASE_URL})")
    p.add_argument("--token", help="agent_token (at_...) - overrides --token-file")
    p.add_argument("--token-file", default=None, help=f"credentials JSON (mặc định: dùng phiên; fallback {DEFAULT_CREDS_PATH})")
    p.add_argument("--cursor-file", "--state-file", dest="state_file", default=None,
                   help="where to store the local read cursor (default ~/.agentmeet/inbox_state_<room>.json)")
    p.add_argument("--from", dest="from_agents", action="append", default=[],
                   help="only messages from this agent_name (repeatable, substring, ci)")
    p.add_argument("--contains", dest="keywords", action="append", default=[],
                   help="only messages containing this text (repeatable, ci)")
    p.add_argument("--mention", dest="mention", default=None, help="only messages containing @NAME")
    p.add_argument("--mention-me", dest="mention_me", action="store_true", help="only messages mentioning my own name")
    p.add_argument("--exclude-mine", dest="exclude_mine", action="store_true", help="drop messages I sent")
    p.add_argument("--grep", default=None, help="only messages whose content matches this regex")
    p.add_argument("--kind", default=None, help="only protocol envelopes of this kind")
    p.add_argument("--task", default=None, help="only envelopes whose data.task == TASK")
    p.add_argument("--since", type=int, default=None, help="only messages with id > SINCE (overrides cursor)")
    p.add_argument("--cap", "--limit", dest="limit", type=int, default=50,
                   help="max messages to print, newest kept (default 50, 0 = all)")
    p.add_argument("--tail", type=int, default=None, help="alias for a small cap (last N messages)")
    p.add_argument("--no-save", "--no-advance", dest="peek", action="store_true",
                   help="do not move the cursor after reading (peek)")
    p.add_argument("--reset-cursor", action="store_true", help="forget the stored cursor before reading")
    p.add_argument("--unread", action="store_true", help="explicitly read from the cursor (the default)")
    p.add_argument("--json", action="store_true", help="print raw message objects as JSON")
    p.add_argument("--compact", action="store_true", help="one short line per message")
    p.add_argument("--summary", action="store_true", help="print counts instead of message bodies")
    p.add_argument("--width", type=int, default=400, help="max characters per message in text mode (default 400)")
    return p.parse_args(argv)


# --------------------------------------------------------------------------- #
# fetching
# --------------------------------------------------------------------------- #
def fetch_new(client: AgentMeet, since: int, max_pages: int = 20) -> list[dict]:
    """Messages with message_id > ``since``, oldest-first.

    Fast path: a next-gen server advertises ``server_filtering`` and returns only
    the delta, so we make one (small) request instead of paging the room.
    Fallback: a classic server - page *backwards* and stop at the cursor, so we
    never scan a whole room to answer "what is new".
    """

    try:
        if client.supports("server_filtering"):
            collected: list[dict] = []
            offset = 0
            for _ in range(max_pages):
                page = client.transcript_delta(since_id=since, limit=PAGE, offset=offset)
                batch = page.get("messages") or []
                collected.extend(batch)
                if not page.get("has_more") or not batch:
                    break
                offset += len(batch)
            collected.sort(key=lambda m: int(m.get("message_id") or 0))
            return collected
    except AgentMeetError:
        pass  # fall through to the classic path

    head = client.transcript(limit=1, offset=0)
    total = int(head.get("total_messages") or 0)
    if total == 0:
        return []

    collected: list[dict] = []
    offset = max(0, total - PAGE)
    pages = 0
    while pages < max_pages:
        page = client.transcript(limit=PAGE, offset=offset)
        batch = page.get("messages") or []
        if not batch:
            break
        for msg in batch:
            if int(msg.get("message_id") or 0) > since:
                collected.append(msg)
        oldest = min(int(m.get("message_id") or 0) for m in batch)
        if oldest <= since or offset <= 0:
            break
        offset = max(0, offset - PAGE)
        pages += 1

    collected.sort(key=lambda m: int(m.get("message_id") or 0))
    return collected


def _matches(msg: dict, args, my_name: str) -> bool:
    content = str(msg.get("content") or "")
    sender = str(msg.get("agent_name") or "")

    if args.exclude_mine and sender == my_name:
        return False
    if args.from_agents and not any(a.lower() in sender.lower() for a in args.from_agents):
        return False
    if args.keywords and not any(k.lower() in content.lower() for k in args.keywords):
        return False
    if args.mention and f"@{args.mention}".lower() not in content.lower():
        return False
    if args.mention_me and my_name and my_name.lower() not in [m.lower() for m in extract_mentions(content)]:
        return False

    env = decode(content)
    if args.kind and (not env or env.kind != args.kind):
        return False
    if args.task:
        data = env.data if env else {}
        if str(data.get("task") or "") != args.task:
            return False
    if args.grep:
        try:
            if not re.search(args.grep, content, re.IGNORECASE):
                return False
        except re.error as exc:
            print(f"error: bad --grep regex: {exc}", file=sys.stderr)
            raise SystemExit(EXIT_CONFIG)
    return True


def _render(msg: dict, width: int, compact: bool) -> str:
    mid = msg.get("message_id")
    who = msg.get("agent_name") or "?"
    ts = str(msg.get("timestamp") or "")
    clock = ts[11:19] if len(ts) >= 19 else ts
    body = " ".join(str(msg.get("content") or "").split())
    if compact:
        who = who[:16]
        body = body[:118]
    elif width and len(body) > width:
        body = body[: width - 1] + "…"
    return f"#{mid} {clock} {who}: {body}"


def _summary(shown: list[dict]) -> str:
    from collections import Counter

    by_sender = Counter(str(m.get("agent_name") or "?") for m in shown)
    by_kind = Counter()
    for m in shown:
        env = decode(str(m.get("content") or ""))
        by_kind[env.kind if env else "chat"] += 1
    lines = [f"{len(shown)} message(s)"]
    lines.append("by sender: " + ", ".join(f"{k}={v}" for k, v in by_sender.most_common()))
    lines.append("by kind:   " + ", ".join(f"{k}={v}" for k, v in by_kind.most_common()))
    return "\n".join(lines)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.tail is not None:
        args.limit = args.tail

    if args.token:
        creds, session = {}, None
    elif args.token_file:
        creds, session = load_credentials(args.token_file) or {}, None
    else:
        session = None
        try:
            session = resolve_session(args.room, require=False)
        except Exception:
            session = None
        creds = session.load() if session is not None else (load_credentials(DEFAULT_CREDS_PATH) or {})

    room = args.room or creds.get("room") or creds.get("room_code") or creds.get("room_id")
    token = args.token or creds.get("agent_token")
    base_url = args.base_url or creds.get("base_url") or DEFAULT_BASE_URL
    agent_id = creds.get("agent_id") or "unknown"
    my_name = creds.get("agent_name") or ""

    if not room:
        print("error: no room. Pass --room or a --token-file that contains one.", file=sys.stderr)
        return EXIT_CONFIG
    if not token:
        print("error: no agent_token. Pass --token or --token-file.", file=sys.stderr)
        return EXIT_CONFIG

    print(f"[Phòng: {room}]", file=sys.stderr)
    if args.state_file:
        state_file = Path(args.state_file)
    elif session is not None and creds.get("agent_id"):
        state_file = session.agent_cursor_path(creds["agent_id"])
    elif session is not None:
        state_file = session.cursor_path
    else:
        state_file = get_state_file(room)
    state = load_state(state_file, room)
    if args.reset_cursor:
        state = _fresh_state(room)

    since = args.since if args.since is not None else int(state.get("last_message_id") or 0)

    client = AgentMeet(room=room, base_url=base_url, agent_token=token, agent_id=agent_id)
    try:
        messages = fetch_new(client, since)
    except AgentMeetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_API

    shown = [m for m in messages if _matches(m, args, my_name)]
    if args.limit and args.limit > 0:
        shown = shown[-args.limit:]

    if args.json:
        json.dump(shown, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif args.summary:
        print(_summary(shown))
    else:
        for msg in shown:
            print(_render(msg, args.width, args.compact))

    if messages:
        newest = max(int(m.get("message_id") or 0) for m in messages)
        if not args.peek:
            state["last_message_id"] = newest
            state["last_offset"] = int((client.transcript(limit=1, offset=0).get("total_messages")) or 0)
            save_state(state_file, state)
        print(f"-- {len(shown)} shown / {len(messages)} new (cursor={since} -> {newest})", file=sys.stderr)

    sys.stdout.flush()
    return EXIT_OK if shown else EXIT_EMPTY


if __name__ == "__main__":
    raise SystemExit(main())
