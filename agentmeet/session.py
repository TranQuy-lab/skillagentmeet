"""Workspace theo phiên (session) cho AgentMeet — stdlib only.

Cấu trúc theo Admin #293 / Lead #333:

    <sessions_root>/<room_id>/
        <agent-slug>/                 MỌI thứ của agent nằm TRONG đây
            creds.json                danh tính (token)
            cursor.json               con trỏ đọc tin
            session.json              metadata phiên của agent
            session.log               nhật ký
            tasks/                    artifacts
            <tệp do agent tạo>        ...

Không còn file ở thư mục gốc room (trừ các thư mục agent). Vẫn ĐỌC được cấu
trúc cũ (``<room>/creds.json``, ``<room>/agents/<id>/``) để migrate.

Không import vòng: module chỉ dùng stdlib.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# đường dẫn
# --------------------------------------------------------------------------- #

def sessions_root() -> Path:
    env = os.environ.get("AGENTMEET_SESSIONS")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".agentmeet" / "sessions"


def active_file() -> Path:
    env = os.environ.get("AGENTMEET_ACTIVE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".agentmeet" / "active.json"


def _legacy_creds_path() -> Path:
    return Path(os.environ.get("AGENTMEET_CREDS", str(Path.home() / ".agentmeet" / "creds.json")))


# --------------------------------------------------------------------------- #
# chuẩn hoá room + slug
# --------------------------------------------------------------------------- #

_ROOM_RE = re.compile(r"([0-9a-zA-Z]{1,12}(?:-[0-9a-zA-Z]{1,12}){1,5})")


def normalize_room(target: str) -> str:
    if not target:
        raise ValueError("thiếu room (link hoặc mã phòng)")
    target = target.strip().strip('"').strip("'")
    target = re.split(r"[?#]", target)[0]
    if "/" in target:
        parts = [p for p in target.split("/") if p]
        candidate = parts[-1] if parts else target
    else:
        candidate = target
    m = _ROOM_RE.search(candidate)
    if not m:
        raise ValueError(f"không nhận diện được mã phòng từ: {target!r}")
    return m.group(1)


def agent_slug(name_or_id: str) -> str:
    s = (name_or_id or "agent").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:48] or "agent"


# --------------------------------------------------------------------------- #
# phiên
# --------------------------------------------------------------------------- #

class Session:
    """Một thư mục làm việc theo phòng; mọi file của agent nằm trong `<room>/<slug>/`."""

    def __init__(self, room: str, root: Optional[Path] = None) -> None:
        self.room = normalize_room(room)
        self.root = Path(root) if root else sessions_root()
        self.dir = self.root / self.room

    # -- discovery -------------------------------------------------------- #
    def ensure(self) -> "Session":
        self.dir.mkdir(parents=True, exist_ok=True)
        return self

    def _scan_agents(self) -> List[Dict[str, Any]]:
        """Quét các thư mục con chứa ``creds.json`` (+ đọc cấu trúc cũ)."""

        found: List[Dict[str, Any]] = []
        if not self.dir.exists():
            return found
        for child in sorted(self.dir.iterdir()):
            if not child.is_dir():
                continue
            creds = child / "creds.json"
            if not creds.exists():
                continue
            try:
                c = json.loads(creds.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                c = {}
            found.append({"agent_id": c.get("agent_id"), "agent_name": c.get("agent_name"),
                          "folder": child.name})
        # cấu trúc cũ <room>/agents/<id>/
        legacy = self.dir / "agents"
        if legacy.is_dir():
            for child in sorted(legacy.iterdir()):
                creds = child / "creds.json"
                if not child.is_dir() or not creds.exists():
                    continue
                try:
                    c = json.loads(creds.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    c = {}
                found.append({"agent_id": c.get("agent_id") or child.name,
                              "agent_name": c.get("agent_name"), "folder": child.name})
        return found

    def agents(self) -> List[Dict[str, Any]]:
        out = []
        for a in self._scan_agents():
            if a.get("agent_id"):
                out.append(a)
        return out

    def find_agent(self, ref: str) -> Optional[str]:
        if not ref:
            return None
        for a in self.agents():
            if ref in (a.get("agent_id"), a.get("agent_name"), a.get("folder")):
                return a.get("agent_id")
        return None

    def agent_dir(self, agent_id: str, agent_name: Optional[str] = None) -> Path:
        for a in self._scan_agents():
            if a.get("agent_id") == agent_id or a.get("folder") == agent_id:
                p = self.dir / a["folder"]
                return p
        return self.dir / agent_slug(agent_name or agent_id)

    def agent_creds_path(self, agent_id: str, agent_name: Optional[str] = None) -> Path:
        return self.agent_dir(agent_id, agent_name) / "creds.json"

    def agent_cursor_path(self, agent_id: str, agent_name: Optional[str] = None) -> Path:
        return self.agent_dir(agent_id, agent_name) / "cursor.json"

    def active_agent_id(self) -> Optional[str]:
        f = active_file()
        if f.exists():
            try:
                a = json.loads(f.read_text(encoding="utf-8"))
                if a.get("room") == self.room and a.get("agent_id"):
                    if any(x["agent_id"] == a["agent_id"] for x in self.agents()):
                        return a["agent_id"]
            except (json.JSONDecodeError, OSError):
                pass
        agents = self.agents()
        return agents[0]["agent_id"] if agents else None

    # -- compatibility properties (trỏ về agent đang hoạt động) ----------- #
    @property
    def active_dir(self) -> Path:
        aid = self.active_agent_id()
        return self.agent_dir(aid) if aid else self.dir

    @property
    def creds_path(self) -> Path:
        return self.active_dir / "creds.json"

    @property
    def cursor_path(self) -> Path:
        return self.active_dir / "cursor.json"

    @property
    def log_path(self) -> Path:
        return self.active_dir / "session.log"

    @property
    def manifest_path(self) -> Path:
        return self.active_dir / "session.json"

    # -- save / load ------------------------------------------------------ #
    def save(self, data: Dict[str, Any]) -> Path:
        """Lưu danh tính vào `<room>/<slug>/creds.json` (+ metadata), KHÔNG để file ở root."""

        self.ensure()
        data = dict(data)
        data.setdefault("service", "agentmeet")
        data["room"] = self.room
        data["room_code"] = self.room
        data["room_id"] = self.room
        aid = data.get("agent_id")
        if not aid:
            raise ValueError("thiếu agent_id khi lưu danh tính phiên")

        name = data.get("agent_name") or aid
        existing = self._scan_agents()
        entry = next((a for a in existing if a.get("agent_id") == aid), None)
        if entry:
            folder = entry["folder"]
        else:
            base = agent_slug(name)
            clash = any(a.get("folder") == base and a.get("agent_id") != aid for a in existing)
            folder = f"{base}-{aid[-4:]}" if clash else base

        adir = self.dir / folder
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "tasks").mkdir(exist_ok=True)
        (adir / "creds.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._chmod600(adir / "creds.json")
        (adir / "session.json").write_text(
            json.dumps({"room": self.room, "agent_id": aid, "agent_name": name,
                        "updated_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # ghi active (không tạo file rác ở root room)
        active_file().parent.mkdir(parents=True, exist_ok=True)
        active_file().write_text(json.dumps({"room": self.room, "agent_id": aid}), encoding="utf-8")
        self.cleanup_legacy_root(aid, name)
        return adir / "creds.json"

    def cleanup_legacy_root(self, agent_id: str, name: Optional[str] = None) -> None:
        """Dọn dữ liệu cũ ở root room vào folder agent (chỉ khi bản trong folder đầy đủ)."""

        adir = self.agent_dir(agent_id, name)
        if not (adir / "creds.json").exists():
            return
        # gộp tasks/ cũ
        legacy_tasks = self.dir / "tasks"
        if legacy_tasks.is_dir():
            (adir / "tasks").mkdir(exist_ok=True)
            for item in legacy_tasks.iterdir():
                try:
                    item.replace(adir / "tasks" / item.name)
                except OSError:
                    pass
            try:
                legacy_tasks.rmdir()
            except OSError:
                pass
        # gộp session.log cũ
        legacy_log = self.dir / "session.log"
        if legacy_log.exists():
            try:
                with legacy_log.open("r", encoding="utf-8", errors="replace") as src, \
                        (adir / "session.log").open("a", encoding="utf-8") as dst:
                    dst.write(src.read())
                legacy_log.unlink()
            except OSError:
                pass
        # bỏ file cũ ở root (mirror) — KHÔNG xóa creds trong folder agent
        for stale in ("creds.json", "cursor.json", "session.json"):
            p = self.dir / stale
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass

    def load(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        aid = agent_id or self.active_agent_id()
        if aid:
            p = self.agent_creds_path(aid)
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
        # cấu trúc cũ ở root room
        old_root = self.dir / "creds.json"
        if old_root.exists():
            try:
                data = json.loads(old_root.read_text(encoding="utf-8"))
                if not agent_id or data.get("agent_id") in (None, agent_id):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        old = self._load_legacy_home()
        if old and (not agent_id or old.get("agent_id") == agent_id):
            return old
        return {}

    def _load_legacy_home(self) -> Dict[str, Any]:
        path = _legacy_creds_path()
        if not path.exists():
            return {}
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        old_room = old.get("room") or old.get("room_code") or old.get("room_id")
        if not old_room or normalize_room(str(old_room)) != self.room:
            return {}
        return dict(old)

    def set_active_agent(self, ref: str) -> Dict[str, Any]:
        aid = self.find_agent(ref) or ref
        data = self.load(aid)
        if not data:
            raise KeyError(f"không thấy agent {ref!r} trong phiên {self.room}")
        active_file().parent.mkdir(parents=True, exist_ok=True)
        active_file().write_text(json.dumps({"room": self.room, "agent_id": aid}), encoding="utf-8")
        return data

    # -- cursor ----------------------------------------------------------- #
    def load_cursor(self, agent_id: Optional[str] = None) -> int:
        aid = agent_id or self.active_agent_id()
        if aid:
            p = self.agent_cursor_path(aid)
            if p.exists():
                try:
                    return int(json.loads(p.read_text(encoding="utf-8")).get("last_message_id") or 0)
                except (json.JSONDecodeError, OSError, ValueError):
                    pass
        return 0

    def save_cursor(self, last_message_id: int, agent_id: Optional[str] = None,
                    agent_name: Optional[str] = None) -> Path:
        self.ensure()
        aid = agent_id or self.active_agent_id()
        d = self.agent_dir(aid, agent_name) if aid else self.dir
        d.mkdir(parents=True, exist_ok=True)
        payload = {"room": self.room, "agent_id": aid, "agent_name": agent_name,
                   "last_message_id": int(last_message_id or 0),
                   "updated_at": datetime.now(timezone.utc).isoformat()}
        p = d / "cursor.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    # -- log -------------------------------------------------------------- #
    def log(self, action: str, detail: str = "") -> None:
        aid = self.active_agent_id()
        d = self.agent_dir(aid) if aid else self.dir
        try:
            d.mkdir(parents=True, exist_ok=True)
            with (d / "session.log").open("a", encoding="utf-8") as fh:
                fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {action}: {detail}\n")
        except OSError:
            pass

    @staticmethod
    def _chmod600(path: Path) -> None:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def mark_active(self) -> Path:
        aid = self.active_agent_id()
        active_file().parent.mkdir(parents=True, exist_ok=True)
        active_file().write_text(json.dumps({"room": self.room, "agent_id": aid}), encoding="utf-8")
        return active_file()


# --------------------------------------------------------------------------- #
# tiện ích cấp module
# --------------------------------------------------------------------------- #

def session_for(room: str, root: Optional[Path] = None) -> Session:
    return Session(normalize_room(room), root=root)


def active_room() -> Optional[str]:
    f = active_file()
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("room")
    except (json.JSONDecodeError, OSError):
        return None


def latest_session(root: Optional[Path] = None) -> Optional[Session]:
    act = active_room()
    if act:
        s = Session(act, root=root)
        if s.agents() or s.dir.exists():
            return s
    base = Path(root) if root else sessions_root()
    if not base.exists():
        return None
    best: Optional[Tuple[float, Session]] = None
    for child in base.iterdir():
        if not child.is_dir():
            continue
        stamp = child.stat().st_mtime
        for probe in child.rglob("creds.json"):
            try:
                stamp = max(stamp, probe.stat().st_mtime)
            except OSError:
                pass
        s = Session(child.name, root=base)
        if best is None or stamp > best[0]:
            best = (stamp, s)
    return best[1] if best else None


def resolve_session(room: Optional[str] = None, require: bool = True) -> Optional[Session]:
    if room:
        return Session(room)
    s = latest_session()
    if s is not None:
        return s
    legacy = _legacy_creds_path()
    if legacy.exists():
        try:
            old = json.loads(legacy.read_text(encoding="utf-8"))
            old_room = old.get("room") or old.get("room_code") or old.get("room_id")
            if old_room:
                return Session(str(old_room))
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    if require:
        raise RuntimeError("chưa có phiên nào — chạy `python -m agentmeet join <room|url>` trước")
    return None


def list_sessions(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    base = Path(root) if root else sessions_root()
    out: List[Dict[str, Any]] = []
    if not base.exists():
        return out
    act = active_room()
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        s = Session(child.name, root=base)
        agents = s.agents()
        if not agents:
            continue
        agent = s.load()
        out.append({"room": child.name, "agent_name": agent.get("agent_name"),
                    "agent_id": agent.get("agent_id"), "agents": agents,
                    "last_message_id": s.load_cursor(), "active": child.name == act})
    return out
