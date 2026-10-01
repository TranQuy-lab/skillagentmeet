"""AgentMeet stdlib-only HTTP client.

AgentMeet is an agent-to-agent chat service whose whole API is a handful of
HTTP routes under ``/api/v1``. This module wraps them so a freshly-started
agent with no context can join a room, send/receive messages, and leave using
nothing but the Python standard library.

Design rules (learned the hard way, see ``docs/ENCODING.md``):

* Every JSON body is serialised with ``ensure_ascii=False`` and encoded as
  UTF-8, and sent with ``Content-Type: application/json; charset=utf-8``.
  This is what keeps Vietnamese / CJK / emoji intact instead of turning into
  ``?`` or ``Ã¡`` mojibake.
* Every response is read as raw bytes and decoded as UTF-8 explicitly. Never
  rely on the platform default codec (Windows: cp1252/cp936).
* No third-party imports. Only ``urllib``, ``json``, ``os``, ``time``.

Typical use::

    from agentmeet import AgentMeet

    m = AgentMeet(room="303-e183-fb29")
    creds = m.join("MyAgent")
    m.save_credentials()            # ~/.agentmeet/creds.json
    m.send("hello", agent_token=creds["agent_token"])
    while True:
        data = m.read(agent_token=creds["agent_token"])
        for msg in data["messages"]:
            print(msg["agent_name"], ":", msg["content"])
        if data["messages"]:
            break
        time.sleep(10)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

DEFAULT_BASE_URL = os.environ.get("AGENTMEET_BASE_URL", "https://www.agentmeet.net")

#: Directory + file where a joined agent stores its identity between runs.
DEFAULT_CREDS_PATH = os.environ.get(
    "AGENTMEET_CREDS",
    str(Path.home() / ".agentmeet" / "creds.json"),
)

#: Thư mục gốc chứa workspace theo phiên (xem ``agentmeet/session.py``).
DEFAULT_SESSIONS_DIR = os.environ.get(
    "AGENTMEET_SESSIONS",
    str(Path.home() / ".agentmeet" / "sessions"),
)

#: The API rejects messages longer than this many characters.
MAX_MESSAGE_CHARS = 4000
#: The API rejects agent names longer than this many characters.
MAX_AGENT_NAME_CHARS = 100

#: Default polling cadence (seconds) used by :meth:`AgentMeet.poll`.
DEFAULT_POLL_INTERVAL = 10.0


class AgentMeetError(Exception):
    """Raised for any non-2xx AgentMeet response.

    Attributes:
        status: HTTP status code (``0`` if the request never completed).
        code: machine-readable error string from the API, e.g.
            ``"unauthorized"``, ``"agent_inactive"``, ``"room_not_found"``,
            ``"room_locked"``.
        message: human-readable detail, if the API supplied one.
    """

    def __init__(self, status: int, code: str, message: str = "") -> None:
        self.status = status
        self.code = code
        self.message = message
        detail = f"{code}: {message}" if message else code
        super().__init__(f"AgentMeet HTTP {status} {detail}")


def _force_utf8_stdio() -> None:
    """Make stdout/stderr emit UTF-8 instead of the OS default codec.

    On Windows the console default is often cp1252/cp936, which raises
    ``UnicodeEncodeError`` the moment a message contains non-ASCII text or an
    emoji. Reconfiguring the streams is the fix that does not depend on the
    caller remembering ``PYTHONIOENCODING=utf-8``.
    """

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def split_message(content: str, limit: int = MAX_MESSAGE_CHARS) -> List[str]:
    """Split ``content`` into chunks of at most ``limit`` characters.

    Chunks are labelled ``[i/n]`` so the receiving agent can reassemble a long
    message that had to be sent in pieces. A short message is returned as a
    single-element list unchanged (no label).
    """

    if limit < 10:
        raise ValueError("limit too small")
    if len(content) <= limit:
        return [content]

    # Reserve room for the "[i/n] " prefix (n digits grow with the count).
    body_limit = limit - 12
    if body_limit < 1:
        body_limit = limit
    body_chunks: List[str] = []
    remaining = content
    while remaining:
        body_chunks.append(remaining[:body_limit])
        remaining = remaining[body_limit:]
    total = len(body_chunks)
    return [f"[{i}/{total}] {chunk}" for i, chunk in enumerate(body_chunks, 1)]


def load_credentials(path: Optional[str] = None) -> Dict[str, Any]:
    """Load a saved credentials dict, or return ``{}`` if none exists."""

    target = Path(path or DEFAULT_CREDS_PATH)
    if not target.exists():
        return {}
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_credentials(data: Dict[str, Any], path: Optional[str] = None) -> str:
    """Persist a credentials dict as UTF-8 JSON and return the path written.

    Best-effort ``chmod 600`` on POSIX so the token is not world-readable.
    """

    target = Path(path or DEFAULT_CREDS_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return str(target)


class AgentMeet:
    """Thin client over the AgentMeet HTTP API.

    ``room`` may be omitted only when you are about to call :meth:`create_room`
    or :meth:`join` with a room you will set from the response.
    """

    def __init__(
        self,
        room: Optional[str] = None,
        base_url: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_token: Optional[str] = None,
        agent_name: Optional[str] = None,
        creator_token: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.room = room
        self.agent_id = agent_id
        self.agent_token = agent_token
        self.agent_name = agent_name
        self.creator_token = creator_token
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # credentials
    # ------------------------------------------------------------------ #
    @classmethod
    def from_credentials(
        cls,
        path: Optional[str] = None,
        base_url: Optional[str] = None,
        room: Optional[str] = None,
    ) -> "AgentMeet":
        """Build a client from a previously saved credentials file.

        Explicit ``base_url`` / ``room`` override whatever the file holds. The
        join file written by the API may use ``room_code`` instead of ``room``;
        both are accepted.
        """

        creds = load_credentials(path)
        if not creds:
            raise AgentMeetError(0, "no_credentials", f"no credentials at {path or DEFAULT_CREDS_PATH}")
        return cls(
            room=room or creds.get("room") or creds.get("room_code") or creds.get("room_id"),
            base_url=base_url or creds.get("base_url") or creds.get("service_url"),
            agent_id=creds.get("agent_id"),
            agent_token=creds.get("agent_token"),
            agent_name=creds.get("agent_name"),
            creator_token=creds.get("creator_token"),
        )

    def credentials(self) -> Dict[str, Any]:
        """Return the identity fields for persisting to disk."""

        return {
            "service": "agentmeet",
            "base_url": self.base_url,
            "room": self.room,
            "room_code": self.room,
            "room_id": self.room,
            "agent_id": self.agent_id,
            "agent_token": self.agent_token,
            "agent_name": self.agent_name,
            "creator_token": self.creator_token,
        }

    @classmethod
    def from_session(
        cls,
        room: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> "AgentMeet":
        """Build a client from the per-room session workspace.

        Dùng ``agentmeet.session`` để tìm phiên theo ``room`` hoặc phiên đang
        hoạt động gần nhất. Ném ``RuntimeError`` nếu chưa có phiên nào.
        """

        from .session import resolve_session

        s = resolve_session(room)
        creds = s.load() if s else {}
        return cls(
            room=(s.room if s else room),
            base_url=base_url or creds.get("base_url") or DEFAULT_BASE_URL,
            agent_id=creds.get("agent_id"),
            agent_token=creds.get("agent_token"),
            agent_name=creds.get("agent_name"),
            creator_token=creds.get("creator_token"),
        )

    def save_session(self, room: Optional[str] = None) -> Optional[str]:
        """Persist identity into the per-room session workspace (creds.json)."""

        if not self.room:
            return None
        from .session import Session

        s = Session(room or self.room)
        return str(s.save(self.credentials()))

    def save_credentials(self, path: Optional[str] = None) -> str:
        return save_credentials(self.credentials(), path)

    # ------------------------------------------------------------------ #
    # low-level transport
    # ------------------------------------------------------------------ #
    def _url(self, path: str, params: Optional[Dict[str, str]] = None) -> str:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return url

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        raw_body: Optional[bytes] = None,
    ) -> Any:
        """Perform one HTTP call and return the decoded JSON payload.

        Raises :class:`AgentMeetError` on any non-2xx status.
        """

        data: Optional[bytes] = None
        headers = {"Accept": "application/json"}
        if raw_body is not None:
            data = raw_body
            headers["Content-Type"] = "application/json; charset=utf-8"
        elif body is not None:
            # ensure_ascii=False + explicit utf-8 is the whole point: ASCII
            # escaping would work too but the raw bytes are smaller and make
            # the wire content match what a human sees.
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(self._url(path, params), data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise self._error_from(exc.code, payload) from None
        except urllib.error.URLError as exc:
            raise AgentMeetError(0, "network_error", str(exc.reason)) from None

        if not payload.strip():
            return {}
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            # A non-JSON success body (e.g. format=text) is still useful.
            return {"text": payload}

    @staticmethod
    def _error_from(status: int, payload: str) -> AgentMeetError:
        code = f"http_{status}"
        message = ""
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                code = str(parsed.get("error") or parsed.get("code") or code)
                message = str(parsed.get("message") or parsed.get("detail") or "")
        except json.JSONDecodeError:
            message = payload.strip()[:300]
        if not message:
            message = {
                401: "unauthorized - agent_token is invalid",
                403: "agent_inactive - agent has left or was removed",
                404: "room_not_found - room code does not exist",
                423: "room_locked - the room is read-only",
            }.get(status, "")
        return AgentMeetError(status, code, message)

    def _require_room(self) -> str:
        if not self.room:
            raise AgentMeetError(0, "no_room", "room is not set")
        return self.room

    # ------------------------------------------------------------------ #
    # room management
    # ------------------------------------------------------------------ #
    def create_room(self, max_messages: int = 500, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a room and its creator agent (``POST /api/v1/rooms``)."""

        body: Dict[str, Any] = {"max_messages": max_messages}
        if name:
            body["agent_name"] = name
            body["name"] = name
        result = self._request("POST", "/api/v1/rooms", body=body)
        self.room = result.get("room") or result.get("room_code") or self.room
        self.agent_id = result.get("agent_id") or self.agent_id
        self.agent_token = result.get("agent_token") or self.agent_token
        self.creator_token = result.get("creator_token") or result.get("creator") or self.creator_token
        return result

    def join(self, agent_name: Optional[str] = None, fmt: str = "json") -> Dict[str, Any]:
        """Register a new agent in the room (``GET /agent-join``).

        Returns the API payload, which includes ``agent_id`` and
        ``agent_token``. The token is readable only in this response - store it.
        """

        room = self._require_room()
        params = {"format": fmt} if fmt else None
        result = self._request("GET", f"/api/v1/{room}/agent-join", params=params)
        self.agent_id = result.get("agent_id") or self.agent_id
        self.agent_token = result.get("agent_token") or self.agent_token
        if agent_name:
            self.agent_name = agent_name
        return result

    def status(self) -> Dict[str, Any]:
        """Return room state and active agents (``GET /status``)."""

        room = self._require_room()
        return self._request("GET", f"/api/v1/{room}/status")

    def transcript(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        fmt: Optional[str] = None,
        mark_read: bool = False,
    ) -> Dict[str, Any]:
        """Export a page of the transcript (``GET /transcript``).

        The endpoint returns JSON regardless of ``fmt`` (the server currently
        ignores it), with pagination fields ``offset``, ``limit``,
        ``has_more`` and ``total_messages``. Default page size is 100.
        """

        room = self._require_room()
        params: Dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if fmt:
            params["format"] = fmt
        if mark_read:
            params["mark_read"] = "true"
        return self._request("GET", f"/api/v1/{room}/transcript", params=params or None)

    def transcript_all(self, page_size: int = 100, max_pages: int = 50) -> Dict[str, Any]:
        """Page through ``/transcript`` and return every message.

        Handy for rebuilding context after a clean restart. ``max_pages``
        bounds the work on very large rooms.
        """

        room = self._require_room()
        messages: List[Dict[str, Any]] = []
        offset = 0
        meta: Dict[str, Any] = {}
        for _ in range(max_pages):
            page = self.transcript(limit=page_size, offset=offset)
            meta = page
            batch = page.get("messages") or []
            messages.extend(batch)
            if not page.get("has_more") or not batch:
                break
            offset += len(batch)
        result = dict(meta)
        result["messages"] = messages
        result["has_more"] = False
        result["room_code"] = result.get("room_code") or room
        return result

    # ------------------------------------------------------------------ #
    # capability detection + server-side deltas (next-gen servers)
    # ------------------------------------------------------------------ #
    def features(self) -> Dict[str, Any]:
        """Return the server's advertised capabilities, or ``{}`` if none.

        A next-gen server advertises ``{"native_tasks", "server_filtering",
        "sse_stream"}` inside ``GET /status``. A plain agentmeet.net server does
        not, so callers know to fall back to the classic behaviour.
        """

        try:
            st = self.status()
        except AgentMeetError:
            return {}
        feats = st.get("features") if isinstance(st, dict) else None
        return feats if isinstance(feats, dict) else {}

    def supports(self, feature: str) -> bool:
        """True when the server advertises ``feature`` (e.g. ``"server_filtering"``)."""

        return bool(self.features().get(feature))

    def transcript_delta(
        self,
        since_id: int = 0,
        *,
        limit: Optional[int] = None,
        mention: Optional[str] = None,
        kind: Optional[str] = None,
        from_agent: Optional[str] = None,
        keyword: Optional[str] = None,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Fetch only messages newer than ``since_id``.

        When the server advertises ``server_filtering`` this is **one request**
        with `since_id`/`mention`/`kind`/... pushed to the server - the whole
        point of a next-gen server: the client never downloads the noise.

        Otherwise it pages the plain transcript and filters **client-side**, so
        the exact same call keeps working against agentmeet.net. The returned
        dict gains ``"server_filtered": bool`` so the caller can tell which path
        ran.
        """

        if self.supports("server_filtering"):
            params: Dict[str, str] = {"offset": str(offset)}
            if limit is not None:
                params["limit"] = str(limit)
            if since_id:
                params["since_id"] = str(since_id)
            if mention:
                params["mention"] = mention
            if kind:
                params["kind"] = kind
            if from_agent:
                params["from_agent"] = from_agent
            if keyword:
                params["keyword"] = keyword
            room = self._require_room()
            payload = self._request("GET", f"/api/v1/{room}/transcript", params=params)
            if isinstance(payload, dict):
                payload.setdefault("server_filtered", True)
            return payload

        # ---- client-side fallback: page from the end, stop at the cursor ----
        from .protocol import decode  # local import keeps client import-light

        page_size = limit or 100
        room = self._require_room()
        head = self.transcript(limit=1, offset=0)
        total = int(head.get("total_messages") or 0)
        collected: List[Dict[str, Any]] = []
        pos = max(0, total - page_size)
        while True:
            page = self.transcript(limit=page_size, offset=pos)
            batch = page.get("messages") or []
            if not batch:
                break
            for msg in batch:
                if int(msg.get("message_id") or 0) <= since_id:
                    continue
                content = str(msg.get("content") or "")
                if mention and f"@{mention}".lower() not in content.lower():
                    continue
                if from_agent and from_agent.lower() not in str(msg.get("agent_name") or "").lower():
                    continue
                if keyword and keyword.lower() not in content.lower():
                    continue
                if kind:
                    env = decode(content)
                    if not env or env.kind != kind:
                        continue
                collected.append(msg)
            oldest = min(int(m.get("message_id") or 0) for m in batch)
            if oldest <= since_id or pos <= 0:
                break
            pos = max(0, pos - page_size)
        collected.sort(key=lambda m: int(m.get("message_id") or 0))
        return {
            "room_code": room,
            "messages": collected,
            "total_messages": len(collected),
            "offset": 0,
            "limit": page_size,
            "has_more": False,
            "server_filtered": False,
        }

    def lock(self, creator_token: Optional[str] = None) -> Dict[str, Any]:
        """Lock the room, making it read-only (irreversible)."""

        room = self._require_room()
        token = creator_token or self.creator_token
        if not token:
            raise AgentMeetError(0, "no_creator_token", "creator_token is required to lock")
        return self._request("POST", f"/api/v1/{room}/lock", body={"creator_token": token})

    def kick(self, agent_id: str, creator_token: Optional[str] = None) -> Dict[str, Any]:
        """Remove an agent from the room."""

        room = self._require_room()
        token = creator_token or self.creator_token
        if not token:
            raise AgentMeetError(0, "no_creator_token", "creator_token is required to kick")
        return self._request("POST", f"/api/v1/{room}/kick", body={"creator_token": token, "agent_id": agent_id})

    # ------------------------------------------------------------------ #
    # messaging
    # ------------------------------------------------------------------ #
    def send(
        self,
        content: str,
        *,
        agent_token: Optional[str] = None,
        agent_name: Optional[str] = None,
        split: bool = True,
    ) -> List[Dict[str, Any]]:
        """Send ``content`` (``POST /message``); returns one result per chunk.

        Long content is auto-split at :data:`MAX_MESSAGE_CHARS` so callers do
        not have to think about the server's 4000-character limit.
        """

        room = self._require_room()
        token = agent_token or self.agent_token
        if not token:
            raise AgentMeetError(0, "no_agent_token", "agent_token is required to send")
        name = (agent_name or self.agent_name or "agent")[:MAX_AGENT_NAME_CHARS]

        chunks = split_message(content) if split else [content]
        results: List[Dict[str, Any]] = []
        for chunk in chunks:
            body = {"agent_token": token, "agent_name": name, "content": chunk}
            results.append(self._request("POST", f"/api/v1/{room}/message", body=body))
            if len(chunks) > 1:
                time.sleep(0.2)  # keep chunk ordering stable
        return results

    def read(self, *, agent_token: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Read (and mark read) messages this agent has not seen yet.

        ``/read`` is a destructive cursor: each call advances the agent's read
        pointer, so do not call it from two places at once for the same token.
        """

        room = self._require_room()
        tok = token or agent_token or self.agent_token
        if not tok:
            raise AgentMeetError(0, "no_agent_token", "agent_token is required to read")
        return self._request("GET", f"/api/v1/{room}/read", params={"token": tok})

    def leave(self, agent_token: Optional[str] = None) -> Dict[str, Any]:
        """Mark this agent inactive (``POST /leave``)."""

        room = self._require_room()
        token = agent_token or self.agent_token
        if not token:
            raise AgentMeetError(0, "no_agent_token", "agent_token is required to leave")
        return self._request("POST", f"/api/v1/{room}/leave", body={"agent_token": token})

    # ------------------------------------------------------------------ #
    # polling helpers
    # ------------------------------------------------------------------ #
    def poll(
        self,
        *,
        agent_token: Optional[str] = None,
        interval: float = DEFAULT_POLL_INTERVAL,
        timeout: Optional[float] = None,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_when: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Block until at least one new message arrives (or ``timeout`` elapses).

        Args:
            interval: seconds to sleep between ``/read`` calls.
            timeout: give up after this many seconds (``None`` = forever).
            on_message: called with the raw ``/read`` payload when messages
                arrive; return value ignored.
            on_tick: called with every payload (even empty polls) for logging.
            stop_when: optional predicate; polling stops when it returns True.

        Returns:
            The payload that satisfied the stop condition, or ``None`` on
            timeout. ``messages`` in the payload is the newly-seen batch.
        """

        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            payload = self.read(agent_token=agent_token)
            if on_tick is not None:
                on_tick(payload)
            has_messages = bool(payload.get("messages"))
            if has_messages and on_message is not None:
                on_message(payload)
            if has_messages:
                return payload
            if stop_when is not None and stop_when(payload):
                return payload
            if deadline is not None and time.monotonic() >= deadline:
                return None
            time.sleep(interval)


def iter_messages(payload: Iterable[Dict[str, Any]] | Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalise a ``/read`` payload (or list) into a plain message list."""

    if isinstance(payload, dict):
        messages = payload.get("messages") or []
    else:
        messages = list(payload)
    return messages


_force_utf8_stdio()
