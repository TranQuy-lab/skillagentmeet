#!/usr/bin/env python3
"""Broadcast a git diff to the room for adversarial cross-check.

Sharing a diff is the core of multi-agent code review. This tool runs ``git
diff`` (or reads a patch file / stdin), splits it into chunks that fit the
4000-character message limit, and posts each chunk as a structured ``diff``
message so the receiving agent can reassemble it.

Examples::

    # Working tree vs HEAD:
    python scripts/send_diff.py --token-file creds.json --label "PR2 fix"

    # A commit range:
    python scripts/send_diff.py --token-file creds.json --range b2267ee..HEAD --task T1a2b3

    # A saved patch:
    python scripts/send_diff.py --token-file creds.json --file pr34.diff

    # Staged changes only:
    python scripts/send_diff.py --token-file creds.json --staged
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import (  # noqa: E402
    AgentMeet,
    AgentMeetError,
    DEFAULT_BASE_URL,
    DEFAULT_CREDS_PATH,
    encode,
    load_credentials,
)

EXIT_OK = 0
EXIT_CONFIG = 3
EXIT_API = 4

#: Leave headroom for the protocol envelope inside the 4000-char API limit.
DEFAULT_CHUNK = 3200


def chunk_text(text: str, limit: int = DEFAULT_CHUNK):
    """Split ``text`` on line boundaries into <=``limit`` chunks.

    A single line longer than ``limit`` is hard-split so nothing is dropped.
    """

    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks or [""]


def get_diff(args) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    if args.stdin:
        return sys.stdin.buffer.read().decode("utf-8", errors="replace")
    cmd = ["git", "-C", args.repo, "diff"]
    if args.staged:
        cmd.append("--staged")
    elif args.range:
        cmd.append(args.range)
    if args.paths:
        cmd.append("--")
        cmd.extend(args.paths)
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"git diff failed: {proc.stderr.decode('utf-8', errors='replace').strip()}")
    return proc.stdout.decode("utf-8", errors="replace")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Send a chunked git diff to an AgentMeet room.")
    p.add_argument("--room")
    p.add_argument("--base-url", default=None, help=f"API origin (default {DEFAULT_BASE_URL})")
    p.add_argument("--token")
    p.add_argument("--token-file", default=DEFAULT_CREDS_PATH)
    p.add_argument("--as", dest="as_name", help="agent name to post as (default: from creds)")
    p.add_argument("--repo", default=".", help="git repository path")
    p.add_argument("--range", help="git diff range, e.g. b2267ee..HEAD")
    p.add_argument("--staged", action="store_true", help="diff the staged index")
    p.add_argument("--file", help="read the patch from this file instead of running git")
    p.add_argument("--stdin", action="store_true", help="read the patch from stdin")
    p.add_argument("--task", help="task id this diff belongs to")
    p.add_argument("--label", help="human label for the diff")
    p.add_argument("--paths", nargs="*", help="limit to these paths")
    p.add_argument("--chunk", type=int, default=DEFAULT_CHUNK, help=f"chunk size (default {DEFAULT_CHUNK})")
    p.add_argument("--dry-run", action="store_true", help="print stats, do not send")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    diff = get_diff(args)
    if not diff.strip():
        print("no diff to send")
        return EXIT_OK

    files = [ln[6:] for ln in diff.splitlines() if ln.startswith("+++ b/") or ln.startswith("--- a/")]
    files = sorted(dict.fromkeys(f for f in files if f != "/dev/null"))
    label = args.label or args.range or ("staged" if args.staged else "working-tree")

    creds = {} if args.token else load_credentials(args.token_file)
    room = args.room or creds.get("room") or creds.get("room_code") or creds.get("room_id")
    token = args.token or creds.get("agent_token")
    base_url = args.base_url or creds.get("base_url") or DEFAULT_BASE_URL
    name = args.as_name or creds.get("agent_name") or "agent"

    # JSON-encoding escapes newlines and quotes, so the encoded message is
    # larger than the raw patch. Shrink the chunk until every message fits the
    # API's 4000-char ceiling.
    limit = args.chunk
    while True:
        chunks = chunk_text(diff, limit)
        total = len(chunks)
        payloads = [
            encode("diff", {"task": args.task, "label": label, "part": f"{i}/{total}",
                            "files": files, "patch": c, "by": name})
            for i, c in enumerate(chunks, 1)
        ]
        if max((len(p) for p in payloads), default=0) <= 3900 or limit <= 400:
            break
        limit = int(limit * 0.8)
    print(f"diff {len(diff)} chars, {len(files)} file(s), {len(chunks)} chunk(s) @ {limit}: {', '.join(files)[:200]}")

    if args.dry_run:
        return EXIT_OK

    if not room or not token:
        print("error: need room and agent_token (--room/--token or --token-file)", file=sys.stderr)
        return EXIT_CONFIG

    client = AgentMeet(room=room, base_url=base_url, agent_token=token, agent_name=name)
    try:
        for msg in payloads:
            client.send(msg, agent_token=token, agent_name=name, split=False)
    except AgentMeetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_API
    print(f"sent {total} diff chunk(s) as {name}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
