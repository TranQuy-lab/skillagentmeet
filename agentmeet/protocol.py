"""Structured message protocol for multi-agent work, layered on plain chat.

AgentMeet only carries text. For a team of agents that split *coding* work we
need messages a program can read: who owns which task, which files are claimed,
whether a review passed, and whether a member dissents. This module defines a
tiny JSON envelope that rides inside a normal message so:

* agents that understand the protocol get machine-parseable team state;
* agents that do not still receive human-readable text;
* plain chat messages decode to ``None`` and never break the room.

Envelope shape (one JSON object, encoded as UTF-8 text)::

    {"v": 1, "kind": "task", "id": "T1a2b3", "ts": "2026-...Z", "data": {...}}

``kind`` is one of the constants below; ``data`` is kind-specific. Every
message sent via :func:`encode` is also prefixed with a short human banner so
the room stays readable in the AgentMeet web UI.

Typical use::

    from agentmeet.protocol import encode, decode, build_board
    import json

    room.send(encode("task", {"task": "T1", "title": "fix CTE", "files": ["order.go"]}))

    board = build_board(messages)          # messages: list of /read or /transcript items
    print(json.dumps(board, ensure_ascii=False, indent=2))
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

PROTOCOL_VERSION = 1

# --- message kinds ------------------------------------------------------- #
KIND_HELLO = "hello"        # announce identity / role / capabilities
KIND_TASK = "task"          # create or update a task
KIND_CLAIM = "claim"        # claim ownership of a task
KIND_STATUS = "status"      # progress / state transition on a task
KIND_REVIEW = "review"      # adversarial review verdict on a task
KIND_BLOCK = "block"        # declare a task blocked
KIND_DISSENT = "dissent"    # member veto / objection (always allowed)
KIND_PROPOSAL = "proposal"  # propose a decision
KIND_VOTE = "vote"          # vote on a proposal or candidate
KIND_LEAD = "lead"          # team-lead nominate / vote / declare
KIND_HANDOFF = "handoff"    # context pack for a clean-context restart
KIND_DIFF = "diff"          # a chunk of a diff/patch for cross-check
KIND_ACK = "ack"            # acknowledge receipt
KIND_VERIFY = "verify"      # independent verification verdict (pass/fail)
KIND_HEARTBEAT = "heartbeat"  # liveness / periodic status beat
KIND_CONTROL = "control"    # loop control: stop / resume / scope-freeze
KIND_CLEAR_DISSENT = "clear_dissent"  # clear member objection after resolution

ALL_KINDS = (
    KIND_HELLO, KIND_TASK, KIND_CLAIM, KIND_STATUS, KIND_REVIEW, KIND_BLOCK,
    KIND_DISSENT, KIND_PROPOSAL, KIND_VOTE, KIND_LEAD, KIND_HANDOFF,
    KIND_DIFF, KIND_ACK, KIND_VERIFY, KIND_HEARTBEAT, KIND_CONTROL,
    KIND_CLEAR_DISSENT,
)

# --- task states --------------------------------------------------------- #
OPEN = "open"
CLAIMED = "claimed"
DOING = "doing"
REVIEW = "review"
DONE = "done"
BLOCKED = "blocked"
STATES = (OPEN, CLAIMED, DOING, REVIEW, DONE, BLOCKED)

#: Emoji used when rendering a protocol message back as plain text.
_KIND_ICON = {
    KIND_HELLO: "👋", KIND_TASK: "📋", KIND_CLAIM: "🙋", KIND_STATUS: "📈",
    KIND_REVIEW: "🔍", KIND_BLOCK: "⛔", KIND_DISSENT: "⚠️", KIND_PROPOSAL: "💡",
    KIND_VOTE: "🗳️", KIND_LEAD: "👑", KIND_HANDOFF: "📦", KIND_DIFF: "🧩",
    KIND_ACK: "✅", KIND_VERIFY: "🔬", KIND_HEARTBEAT: "💓", KIND_CONTROL: "🎛️",
    KIND_CLEAR_DISSENT: "🕊️",
}


def new_id(prefix: str = "T") -> str:
    """Short, collision-resistant id for tasks/messages (6 hex chars)."""

    return f"{prefix}{secrets.token_hex(3)}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Envelope:
    """A decoded protocol message."""

    kind: str
    data: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    ts: Optional[str] = None
    v: int = PROTOCOL_VERSION
    raw: str = ""

    def to_text(self, banner: bool = True) -> str:
        """Serialise back to the text that goes on the wire."""

        payload = {"v": self.v, "kind": self.kind, "id": self.id, "ts": self.ts or _utc_now(), "data": self.data}
        body = json.dumps(payload, ensure_ascii=False)
        if not banner:
            return body
        return f"{_KIND_ICON.get(self.kind, '•')} [{self.kind}] {body}"


def encode(
    kind: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    msg_id: Optional[str] = None,
    ts: Optional[str] = None,
    banner: bool = True,
) -> str:
    """Build a protocol message ready to pass to ``AgentMeet.send``."""

    if kind not in ALL_KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {ALL_KINDS}")
    return Envelope(kind=kind, data=data or {}, id=msg_id, ts=ts).to_text(banner=banner)


def decode_all(text: str) -> List[Envelope]:
    """Parse all valid JSON envelopes found in a message body."""
    if not text:
        return []
    envs: List[Envelope] = []
    dec = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        brace = text.find("{", idx)
        if brace == -1:
            break
        try:
            parsed, end = dec.raw_decode(text[brace:])
            idx = brace + end
            if isinstance(parsed, dict):
                kind = parsed.get("kind")
                if isinstance(kind, str) and kind in ALL_KINDS:
                    data = parsed.get("data")
                    if not isinstance(data, dict):
                        data = {}
                    envs.append(
                        Envelope(
                            kind=kind,
                            data=data,
                            id=parsed.get("id"),
                            ts=parsed.get("ts"),
                            v=int(parsed.get("v") or PROTOCOL_VERSION),
                            raw=text[brace:idx],
                        )
                    )
        except json.JSONDecodeError:
            idx = brace + 1
    return envs


def decode(text: str) -> Optional[Envelope]:
    """Parse the first valid Envelope in a message body, or None."""
    envs = decode_all(text)
    return envs[0] if envs else None


def is_protocol(text: str) -> bool:
    return decode(text) is not None


def render_human(env: Envelope) -> str:
    """One-line human summary of an envelope (for CLI output)."""

    d = env.data
    if env.kind == KIND_TASK:
        return f"TASK {d.get('task', '?')}: {d.get('title', '')} files={d.get('files', [])}"
    if env.kind == KIND_CLAIM:
        return f"CLAIM {d.get('task', '?')} by {d.get('by', '?')}"
    if env.kind == KIND_STATUS:
        return f"STATUS {d.get('task', '?')} -> {d.get('state', '?')} {d.get('note', '')}".rstrip()
    if env.kind == KIND_REVIEW:
        return f"REVIEW {d.get('task', '?')} {d.get('verdict', '?')} by {d.get('by', '?')}"
    if env.kind == KIND_DISSENT:
        return f"DISSENT on {d.get('task') or d.get('on', '?')}: {d.get('reason', '')}"
    if env.kind == KIND_BLOCK:
        return f"BLOCK {d.get('task', '?')}: {d.get('reason', '')}"
    if env.kind == KIND_LEAD:
        return f"LEAD {d.get('action', '?')} candidate={d.get('candidate') or d.get('lead') or '?'} by {d.get('by', '?')}"
    if env.kind == KIND_HANDOFF:
        return f"HANDOFF head={d.get('git_head', '?')} files={len(d.get('files', []))}"
    if env.kind == KIND_DIFF:
        return f"DIFF {d.get('task', d.get('label', '?'))} part={d.get('part', '?')}"
    if env.kind == KIND_VERIFY:
        return f"VERIFY {d.get('task', '?')} {d.get('verdict', '?')} by {d.get('by', '?')}"
    if env.kind == KIND_HEARTBEAT:
        return f"HEARTBEAT {d.get('by', '?')}: {d.get('task', '-')} {d.get('state', '')}".rstrip()
    if env.kind == KIND_CONTROL:
        return f"CONTROL {d.get('action', '?')} by {d.get('by', '?')}"
    if env.kind == KIND_CLEAR_DISSENT:
        return f"CLEAR_DISSENT {d.get('task', '?')} by {d.get('by', '?')}"
    return f"{env.kind.upper()} {json.dumps(d, ensure_ascii=False)[:120]}"


# ------------------------------------------------------------------------ #
# team state folding
# ------------------------------------------------------------------------ #
@dataclass
class TaskState:
    id: str
    title: str = ""
    files: List[str] = field(default_factory=list)
    status: str = OPEN
    owner: Optional[str] = None
    reviewers: List[str] = field(default_factory=list)
    created_by: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    dissent: List[str] = field(default_factory=list)
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    #: Set by a ``verify`` envelope with ``verdict: pass`` from a non-owner.
    #: A task must be verified before it is considered truly done.
    verified: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "files": self.files,
            "status": self.status, "owner": self.owner, "reviewers": self.reviewers,
            "created_by": self.created_by, "notes": self.notes,
            "dissent": self.dissent, "reviews": self.reviews,
            "verified": self.verified,
        }


def _iter_envelopes(messages: Iterable[Dict[str, Any]]):
    for m in messages:
        for env in decode_all(m.get("content", "")):
            yield m, env


def build_board(messages: Iterable[Dict[str, Any]]) -> Dict[str, TaskState]:
    """Fold a room transcript into the current task board.

    ``messages`` is any iterable of dicts with ``content`` and optionally
    ``agent_name`` (exactly what ``/read`` and ``/transcript`` return).
    """

    board: Dict[str, TaskState] = {}
    for msg, env in _iter_envelopes(messages):
        sender = msg.get("agent_name")
        d = env.data
        if env.kind == KIND_TASK:
            tid = d.get("task") or d.get("id") or env.id
            if not tid:
                continue
            t = board.setdefault(tid, TaskState(id=tid))
            if d.get("title"):
                t.title = d["title"]
            if d.get("files"):
                t.files = list(dict.fromkeys([*t.files, *d["files"]]))
            if d.get("owner"):
                t.owner = d["owner"]
            if d.get("reviewers"):
                t.reviewers = list(dict.fromkeys([*t.reviewers, *d["reviewers"]]))
            if d.get("state") in STATES:
                t.status = d["state"]
            t.created_by = t.created_by or d.get("by") or sender
            if d.get("note"):
                t.notes.append(str(d["note"]))
        elif env.kind == KIND_CLAIM:
            tid = d.get("task")
            if tid and tid in board:
                board[tid].owner = d.get("by") or sender
                board[tid].status = CLAIMED
        elif env.kind == KIND_STATUS:
            tid = d.get("task")
            if tid and tid in board and d.get("state") in STATES:
                board[tid].status = d["state"]
                if d.get("note"):
                    board[tid].notes.append(str(d["note"]))
        elif env.kind == KIND_REVIEW:
            tid = d.get("task")
            if tid and tid in board:
                who = d.get("by") or sender
                if who and who not in board[tid].reviewers:
                    board[tid].reviewers.append(who)
                board[tid].reviews.append({"by": who, "verdict": d.get("verdict"), "note": d.get("note", "")})
                board[tid].status = REVIEW
        elif env.kind == KIND_BLOCK:
            tid = d.get("task")
            if tid and tid in board:
                board[tid].status = BLOCKED
                if d.get("reason"):
                    board[tid].notes.append("BLOCKED: " + str(d["reason"]))
        elif env.kind == KIND_DISSENT:
            tid = d.get("task") or d.get("on")
            if tid and tid in board:
                board[tid].dissent.append(f"{d.get('by') or sender}: {d.get('reason', '')}")
        elif env.kind == KIND_CLEAR_DISSENT:
            tid = d.get("task") or d.get("on")
            if tid and tid in board:
                who = d.get("by") or sender
                reason = d.get("reason", "")
                board[tid].dissent.clear()
                board[tid].notes.append(f"DISSENT CLEARED by {who}" + (f": {reason}" if reason else ""))
        elif env.kind == KIND_VERIFY:
            tid = d.get("task")
            if tid and tid in board:
                who = d.get("by") or sender
                verdict = str(d.get("verdict") or "").lower()
                is_author = (
                    board[tid].owner
                    and who
                    and (
                        who == board[tid].owner
                        or who.lower() == str(board[tid].owner).lower()
                    )
                )
                if is_author:
                    board[tid].notes.append(f"INVALID VERIFY: author {who} cannot self-verify task {tid}")
                    continue
                if who and who not in board[tid].reviewers:
                    board[tid].reviewers.append(who)
                board[tid].reviews.append(
                    {"by": who, "verdict": verdict, "note": d.get("note", ""), "kind": "verify"}
                )
                if verdict == "pass":
                    board[tid].verified = True
                elif verdict == "fail":
                    board[tid].verified = False
                    if d.get("note"):
                        board[tid].notes.append("VERIFY FAIL: " + str(d["note"]))
        elif env.kind == KIND_CONTROL:
            tid = d.get("task")
            if tid and tid in board and d.get("action"):
                board[tid].notes.append("CONTROL: " + str(d["action"]))
        # KIND_HEARTBEAT carries no task state; it exists so liveness is visible.
    return board


def board_summary(board: Dict[str, TaskState]) -> str:
    """Render a board as a compact markdown table."""

    if not board:
        return "_(no structured tasks yet)_"
    lines = ["| Task | Status | Owner | Files | Verified | Dissent |", "| --- | --- | --- | --- | --- | --- |"]
    for t in sorted(board.values(), key=lambda x: x.id):
        if t.verified:
            verified = "yes"
        elif t.status == DONE:
            verified = "NO"
        else:
            verified = "-"
        lines.append(
            "| {id} | {status} | {owner} | {files} | {ver} | {dis} |".format(
                id=t.id, status=t.status or OPEN, owner=t.owner or "-",
                files=", ".join(t.files) or "-", ver=verified, dis=len(t.dissent) or "-",
            )
        )
    return "\n".join(lines)


def tally_lead(messages: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Fold ``lead`` envelopes into ``{"declared": ..., "votes": {...}}``.

    A ``declare`` action wins outright; otherwise the candidate with the most
    ``nominate`` + ``vote`` envelopes leads. Ties return ``None`` so the caller
    can trigger another round instead of guessing.
    """

    declared: Optional[str] = None
    votes: Dict[str, List[str]] = {}
    for msg, env in _iter_envelopes(messages):
        if env.kind != KIND_LEAD:
            continue
        d = env.data
        action = d.get("action")
        by = d.get("by") or msg.get("agent_name")
        candidate = d.get("candidate") or d.get("lead")
        if action == "declare" and candidate:
            declared = candidate
        elif candidate:
            votes.setdefault(candidate, [])
            if by and by not in votes[candidate]:
                votes[candidate].append(by)
    if declared:
        return {"declared": declared, "lead": declared, "votes": votes}
    if not votes:
        return {"declared": None, "lead": None, "votes": {}}
    ranked = sorted(votes.items(), key=lambda kv: len(kv[1]), reverse=True)
    top = len(ranked[0][1])
    if len(ranked) > 1 and len(ranked[1][1]) == top:
        tied = [candidate for candidate, voters in ranked if len(voters) == top]
        return {"declared": None, "lead": None, "votes": votes, "tie": tied}
    return {"declared": None, "lead": ranked[0][0], "votes": votes}
