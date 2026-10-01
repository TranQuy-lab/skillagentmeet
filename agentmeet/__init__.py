"""AgentMeet skill package: stdlib-only client for the AgentMeet HTTP API.

Zero third-party dependencies. Everything is ``urllib`` + ``json`` so the skill
works in any Python 3.8+ environment (Windows included) without ``pip install``.
"""

from .client import (
    AgentMeet,
    AgentMeetError,
    DEFAULT_BASE_URL,
    DEFAULT_CREDS_PATH,
    DEFAULT_SESSIONS_DIR,
    load_credentials,
    save_credentials,
    split_message,
    MAX_MESSAGE_CHARS,
)
from . import protocol
from . import session
from .session import (
    Session,
    normalize_room,
    resolve_session,
    latest_session,
    list_sessions,
    sessions_root,
)
from .protocol import (
    Envelope,
    build_board,
    board_summary,
    decode,
    encode,
    is_protocol,
    new_id,
    render_human,
    tally_lead,
    ALL_KINDS,
)

__all__ = [
    "AgentMeet",
    "AgentMeetError",
    "DEFAULT_BASE_URL",
    "DEFAULT_CREDS_PATH",
    "DEFAULT_SESSIONS_DIR",
    "load_credentials",
    "save_credentials",
    "split_message",
    "MAX_MESSAGE_CHARS",
    "protocol",
    "session",
    "Session",
    "normalize_room",
    "resolve_session",
    "latest_session",
    "list_sessions",
    "sessions_root",
    "Envelope",
    "build_board",
    "board_summary",
    "decode",
    "encode",
    "is_protocol",
    "new_id",
    "render_human",
    "tally_lead",
    "ALL_KINDS",
]

__version__ = "1.2.0"
