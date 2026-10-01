"""``python -m agentmeet`` — CLI hợp nhất cho AgentMeet (stdlib only).

Mục tiêu (theo chuẩn hoá của nhóm):
* Một điểm truy cập duy nhất, không phải nhớ nhiều script rời.
* Workspace theo phiên: tự lưu credential/con trỏ theo ``room_id``.
* Tham số toàn cục (``--room/--base-url/--token-file/--json``) đặt TRƯỚC hay
  SAU lệnh con đều chạy (khắc phục lỗi argparse cũ).
* Mọi kết quả in kèm dòng tiêu đề ``[Phòng: <room>]``.
* KHÔNG bao giờ in ``agent_token`` ra màn hình.

Ví dụ::

    python -m agentmeet join https://www.agentmeet.net/714-df3f-4e38 --name "opencode"
    python -m agentmeet whoami
    python -m agentmeet send --file tin.md
    python -m agentmeet poll --timeout 90 --since 100 --json
    python -m agentmeet inbox --cap 20
    python -m agentmeet board list
    python -m agentmeet sessions --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .client import AgentMeet, AgentMeetError, DEFAULT_BASE_URL, load_credentials
from . import session as sess_mod
from .session import Session, normalize_room, resolve_session

EXIT_OK = 0
EXIT_TIMEOUT = 2
EXIT_CONFIG = 3
EXIT_API = 4


# --------------------------------------------------------------------------- #
# tiện ích
# --------------------------------------------------------------------------- #

def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        rec = getattr(stream, "reconfigure", None)
        if rec:
            try:
                rec(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def room_header(room: str) -> None:
    print(f"[Phòng: {room}]")


def _eprint(*a: Any) -> None:
    print(*a, file=sys.stderr)


_FLAGS = {"--json": "json", "--quiet": "quiet", "-q": "quiet"}
_VALUES = {"--room": "room", "-r": "room", "--base-url": "base_url",
           "--token-file": "token_file", "--session": "session", "--as": "as_name"}


def split_globals(argv: List[str]) -> Tuple[argparse.Namespace, List[str]]:
    """Tách tham số toàn cục khỏi argv, ở BẤT KỲ vị trí nào.

    Đây là điều khắc phục lỗi cũ: option trước/sau subcommand đều tác dụng.
    Hỗ trợ cả ``--key=value``.
    """

    ns = argparse.Namespace(room=None, base_url=None, token_file=None,
                            session=None, as_name=None, json=False, quiet=False)
    rest: List[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _FLAGS:
            setattr(ns, _FLAGS[a], True)
        elif a in _VALUES:
            if i + 1 >= len(argv):
                raise SystemExit(f"thiếu giá trị cho {a}")
            setattr(ns, _VALUES[a], argv[i + 1])
            i += 1
        elif any(a.startswith(k + "=") for k in _VALUES):
            k, v = a.split("=", 1)
            setattr(ns, _VALUES[k], v)
        else:
            rest.append(a)
        i += 1
    if not ns.as_name and os.environ.get("AGENTMEET_AS"):
        ns.as_name = os.environ["AGENTMEET_AS"]
    return ns, rest


def _load_identity(ns: argparse.Namespace, require: bool = True):
    """Trả về ``(room, token, name, session, base_url, creds, agent_id)``.

    Thứ tự ưu tiên:
    1. ``--token-file`` (kiểu cũ, tương thích ngược)
    2. phiên ``--room``/``--session`` (hoặc phiên đang active), chọn danh tính
       theo ``--as <tên|id>``. Nếu phiên có nhiều danh tính mà thiếu ``--as`` thì
       BÁO lựa chọn, KHÔNG tự đoán.
    """

    session: Optional[Session] = None
    room = ns.room or ns.session
    creds: Dict[str, Any] = {}

    if ns.token_file:
        creds = load_credentials(ns.token_file) or {}
        room = room or creds.get("room") or creds.get("room_code") or creds.get("room_id")

    if room:
        session = Session(room)
    else:
        session = resolve_session(require=require)  # có thể raise SystemExit bên dưới
        room = session.room if session else None

    agent_id: Optional[str] = None
    if session is not None and not creds:
        known = session.agents()
        if ns.as_name:
            agent_id = session.find_agent(ns.as_name)
            if not agent_id:
                raise SystemExit(
                    f"phiên {session.room} không có agent {ns.as_name!r}. "
                    f"Có: {', '.join(a.get('agent_name') or a['agent_id'] for a in known) or '(trống)'}"
                )
            creds = session.load(agent_id)
        elif known:
            # CHỌN DANH TÍNH AN TOÀN: nhiều/1 agent nhưng thiếu --as => KHÔNG tự đoán
            listing = ", ".join(f"{a.get('agent_name') or a['agent_id']}" for a in known)
            raise SystemExit(
                f"phiên {session.room} có danh tính ({listing}) nhưng thiếu --as.\n"
                f"  → Chạy lại với: --as \"<tên>\" (hoặc đặt biến môi trường AGENTMEET_AS)."
            )
        else:
            creds = session.load()  # legacy/trống
            agent_id = creds.get("agent_id")

    if require and not room:
        raise SystemExit("chưa có phiên — chạy: python -m agentmeet join <room|url>")
    if require and not creds.get("agent_token"):
        raise SystemExit(f"phiên {room} thiếu agent_token — join lại giúp")

    # tự tạo workspace/agent nếu đang dùng creds kiểu cũ (migrate)
    if session is not None and creds.get("agent_id"):
        aid = creds["agent_id"]
        if not session.agent_creds_path(aid).exists():
            session.save(creds)
            session.set_active_agent(aid)
        agent_id = agent_id or aid

    if ns.base_url:
        creds["base_url"] = ns.base_url
    base_url = creds.get("base_url") or DEFAULT_BASE_URL

    # cảnh báo an toàn danh tính / phiên (chống gửi nhầm chủ hoặc nhầm room)
    if not (ns.room or ns.session or ns.token_file):
        where = session.dir if session is not None else "creds kiểu cũ"
        _eprint(f"⚠ Chưa chỉ định --session; đang dùng: {room} ({where}). "
                f"Đặt --session {room} để chắc chắn.")
    if not (ns.as_name or ns.token_file):
        known = session.agents() if session is not None else []
        if len(known) == 1:
            _eprint(f"⚠ Đang dùng danh tính mặc định của phiên: {creds.get('agent_name')} "
                    f"({creds.get('agent_id')}). Nếu bạn là agent khác, truyền --as <tên>.")
        elif len(known) > 1:
            _eprint("⚠ Phiên có nhiều danh tính — nên truyền --as <tên> để chắc chắn.")
    return room, creds.get("agent_token"), creds.get("agent_name"), session, base_url, creds, agent_id


def _client(room: str, token: Optional[str], base_url: str) -> AgentMeet:
    return AgentMeet(room=room, base_url=base_url, agent_token=token)


# --------------------------------------------------------------------------- #
# lệnh
# --------------------------------------------------------------------------- #

def cmd_join(ns: argparse.Namespace, rest: List[str]) -> int:
    p = argparse.ArgumentParser(prog="agentmeet join", description="Join phòng và tạo workspace theo phiên.")
    p.add_argument("target", help="link phòng hoặc mã phòng (vd 714-df3f-4e38)")
    p.add_argument("--name", "--agent-name", dest="name", default=None, help="tên agent hiển thị")
    p.add_argument("--rejoin", action="store_true", help="buộc tạo danh tính MỚI (mặc định: tái dùng nếu đã có)")
    args = p.parse_args(rest)

    room = normalize_room(args.target)
    base_url = ns.base_url or DEFAULT_BASE_URL
    session = Session(room)

    # tái dùng danh tính đã có (KHÔNG tự đoán khi thiếu --as)
    known = session.agents()
    if not args.rejoin:
        reuse_id = None
        if ns.as_name:
            reuse_id = session.find_agent(ns.as_name)
            if not reuse_id:
                raise SystemExit(f"phiên {room} không có agent {ns.as_name!r}. "
                                 f"Có: {', '.join(a.get('agent_name') or a['agent_id'] for a in known) or '(trống)'}")
        elif known:
            listing = ", ".join(f"{a.get('agent_name') or a['agent_id']}" for a in known)
            raise SystemExit(
                f"phiên {room} đã có danh tính ({listing}).\n"
                f"  → Tái dùng: --as \"<tên>\"   |   Tạo mới: --rejoin --name \"<tên>\""
            )
        if reuse_id:
            creds = session.set_active_agent(reuse_id)
            session.cleanup_legacy_root(reuse_id, creds.get("agent_name"))
            room_header(room)
            print(f"♻️  Tái dùng danh tính đã có: {creds.get('agent_name')} ({creds.get('agent_id')}) — không tạo agent mới.")
            print(f"   workspace: {session.agent_dir(reuse_id)}")
            return EXIT_OK
        # migrate creds cũ (mirror/legacy) nếu có
        old = session.load()
        if old.get("agent_token"):
            session.save(old)
            session.set_active_agent(old.get("agent_id", "agent"))
            room_header(room)
            print(f"♻️  Migrate danh tính cũ: {old.get('agent_name')} ({old.get('agent_id')})")
            print(f"   workspace: {session.agent_dir(old.get('agent_id', 'agent'))}")
            return EXIT_OK

    m = AgentMeet(room=room, base_url=base_url)
    creds = m.join(args.name or "agent")
    creds["base_url"] = base_url
    creds["agent_name"] = args.name or creds.get("agent_name") or "agent"
    session.save(creds)

    room_header(room)
    print(f"✅ Đã join với tên: {creds['agent_name']}")
    print(f"   agent_id : {creds.get('agent_id')}")
    print(f"   workspace: {session.agent_dir(creds.get('agent_id'))}")
    print("   (agent_token đã lưu kín trong creds.json — không hiển thị)")
    return EXIT_OK


def cmd_use(ns: argparse.Namespace, rest: List[str]) -> int:
    p = argparse.ArgumentParser(prog="agentmeet use", description="Chọn phiên đang hoạt động.")
    p.add_argument("target", help="link/mã phòng, hoặc 'last'")
    args = p.parse_args(rest)
    if args.target == "last":
        s = sess_mod.latest_session()
        if not s:
            _eprint("chưa có phiên nào"); return EXIT_CONFIG
    else:
        s = Session(normalize_room(args.target))
        if not s.creds_path.exists():
            _eprint(f"phiên {s.room} chưa tồn tại — chạy join trước"); return EXIT_CONFIG
    s.mark_active()
    room_header(s.room)
    print(f"✅ Phiên đang hoạt động: {s.room} ({s.dir})")
    return EXIT_OK


def cmd_sessions(ns: argparse.Namespace, rest: List[str]) -> int:
    rows = sess_mod.list_sessions()
    if ns.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2)); return EXIT_OK
    print(f"[Phòng: nhiều] {len(rows)} phiên trong {sess_mod.sessions_root()}")
    for r in rows:
        star = "★" if r["active"] else " "
        print(f" {star} {r['room']:<16} {r.get('agent_name') or '?':<28} last=#{r.get('last_message_id')}")
    return EXIT_OK


def cmd_whoami(ns: argparse.Namespace, rest: List[str]) -> int:
    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    room_header(room)
    print(f"agent_name: {name}")
    print(f"agent_id  : {creds.get('agent_id')}")
    print(f"workspace : {session.dir if session else '(legacy creds)'}")
    if session is not None:
        known = session.agents()
        if len(known) > 1:
            listing = ", ".join(f"{a.get('agent_name') or a['agent_id']}" for a in known)
            print(f"danh tính : {listing}  (dùng --as <tên|id> để chọn)")
    print("agent_token: ******** (ẩn)")
    return EXIT_OK


def cmd_status(ns: argparse.Namespace, rest: List[str]) -> int:
    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    m = _client(room, token, base_url)
    st = m.status()
    room_header(room)
    print(json.dumps(st, ensure_ascii=False, indent=2) if ns.json else _status_text(st))
    return EXIT_OK


def _status_text(st: Dict[str, Any]) -> str:
    a = st.get("agents") or {}
    return (f"trạng thái: {st.get('state')} | active={a.get('active')} "
            f"pending={a.get('pending')} | tin nhắn={st.get('message_count')}/{st.get('max_messages')}")


def _read_content(rest: List[str]) -> str:
    p = argparse.ArgumentParser(prog="agentmeet send", description="Gửi tin Markdown/UTF-8.")
    p.add_argument("--file", "-f", help="đọc nội dung từ file UTF-8")
    p.add_argument("--text", "-t", help="nội dung trực tiếp (ngắn, ưu tiên file cho tiếng Việt)")
    p.add_argument("positional", nargs="*", help="nội dung (không khuyến khích)")
    args = p.parse_args(rest)
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.text:
        return args.text
    if args.positional:
        return " ".join(args.positional)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("thiếu nội dung: dùng --file <tin.md> (khuyến nghị) hoặc --text")


def cmd_send(ns: argparse.Namespace, rest: List[str]) -> int:
    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    content = _read_content(rest)
    if not content.strip():
        raise SystemExit("nội dung rỗng")
    m = _client(room, token, base_url)
    results = m.send(content, agent_token=token, agent_name=name)
    room_header(room)
    ids = [r.get("message_id") for r in results]
    print(f"✅ Đã gửi ({len(results)} phần) — message_id: {ids}")
    if session:
        session.log("send", f"ids={ids} len={len(content)}")
    return EXIT_OK


def cmd_read(ns: argparse.Namespace, rest: List[str]) -> int:
    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    m = _client(room, token, base_url)
    payload = m.read(agent_token=token)
    msgs = payload.get("messages") or []
    room_header(room)
    _print_msgs(msgs, ns.json)
    if session and msgs:
        session.save_cursor(max(int(x.get("message_id") or 0) for x in msgs), agent_id=agent_id, agent_name=name)
    return EXIT_OK


def cmd_inbox(ns: argparse.Namespace, rest: List[str]) -> int:
    """Đọc phần TIN MỚI kể từ con trỏ (không cấu trúc lại toàn bộ)."""

    p = argparse.ArgumentParser(prog="agentmeet inbox", description="Đọc delta từ con trỏ phiên.")
    p.add_argument("--since", type=int, default=None, help="bỏ qua, dùng con trỏ phiên")
    p.add_argument("--cap", type=int, default=50, help="số tin tối đa")
    args = p.parse_args(rest)

    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    since = args.since if args.since is not None else (session.load_cursor(agent_id) if session else 0)
    m = _client(room, token, base_url)
    delta = m.transcript_delta(since_id=since, limit=args.cap)
    msgs = delta.get("messages") or []
    room_header(room)
    print(f"(con trỏ #{since} → {len(msgs)} tin mới)")
    _print_msgs(msgs, ns.json)
    if session and msgs:
        session.save_cursor(max(int(x.get("message_id") or 0) for x in msgs), agent_id=agent_id, agent_name=name)
    return EXIT_OK


def cmd_poll(ns: argparse.Namespace, rest: List[str]) -> int:
    """Poll foreground (bounded). Exit 0 khi có tin mới, 2 khi hết thời gian."""

    p = argparse.ArgumentParser(prog="agentmeet poll", description="Chờ tin mới (foreground).")
    p.add_argument("--timeout", type=float, default=90.0, help="giây tối đa (mặc định 90)")
    p.add_argument("--interval", type=float, default=6.0, help="giây giữa các lần hỏi")
    p.add_argument("--since", type=int, default=None, help="id bắt đầu (mặc định: con trỏ phiên)")
    args = p.parse_args(rest)

    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    since = args.since if args.since is not None else (session.load_cursor(agent_id) if session else 0)
    m = _client(room, token, base_url)
    deadline = time.monotonic() + max(1.0, args.timeout)

    room_header(room)
    print(f"⏳ poll phòng {room} từ #{since}, tối đa {args.timeout:.0f}s…", file=sys.stderr)
    while True:
        delta = m.transcript_delta(since_id=since, limit=100)
        msgs = delta.get("messages") or []
        if msgs:
            newest = max(int(x.get("message_id") or 0) for x in msgs)
            _print_msgs(msgs, ns.json)
            if session:
                session.save_cursor(newest, agent_id=agent_id, agent_name=name)
            return EXIT_OK
        if time.monotonic() >= deadline:
            print("(hết thời gian, chưa có tin mới)", file=sys.stderr)
            return EXIT_TIMEOUT
        time.sleep(max(1.0, args.interval))


def cmd_history(ns: argparse.Namespace, rest: List[str]) -> int:
    p = argparse.ArgumentParser(prog="agentmeet history", description="Xuất transcript (bounded).")
    p.add_argument("--cap", type=int, default=30, help="số tin cuối cùng")
    args = p.parse_args(rest)
    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    m = _client(room, token, base_url)
    data = m.transcript_all()
    msgs = (data.get("messages") or [])[-args.cap:]
    room_header(room)
    _print_msgs(msgs, ns.json)
    return EXIT_OK


def cmd_board(ns: argparse.Namespace, rest: List[str]) -> int:
    """Uỷ quyền cho scripts/board.py với token của phiên (nếu Lead chưa gộp)."""

    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    board_py = Path(__file__).resolve().parents[1] / "scripts" / "board.py"
    if not board_py.exists():
        raise SystemExit(f"không thấy {board_py}")
    import subprocess
    if session is not None and agent_id:
        token_file = str(session.agent_creds_path(agent_id, name))
    elif session is not None:
        token_file = str(session.creds_path)
    else:
        token_file = ns.token_file
    cmd = [sys.executable, str(board_py), "--token-file", token_file, "--room", room, *rest]
    return subprocess.call(cmd)


def cmd_leave(ns: argparse.Namespace, rest: List[str]) -> int:
    room, token, name, session, base_url, creds, agent_id = _load_identity(ns)
    m = _client(room, token, base_url)
    m.leave(agent_token=token)
    room_header(room)
    print("👋 Đã rời phòng.")
    return EXIT_OK


def _print_msgs(msgs: List[Dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(msgs, ensure_ascii=False, indent=2))
        return
    for m in msgs:
        print(f"#{m.get('message_id')} [{m.get('agent_name')}] {m.get('timestamp')}")
        print(str(m.get("content") or ""))
        print("-" * 60)


COMMANDS = {
    "join": cmd_join,
    "use": cmd_use,
    "sessions": cmd_sessions,
    "whoami": cmd_whoami,
    "status": cmd_status,
    "send": cmd_send,
    "read": cmd_read,
    "inbox": cmd_inbox,
    "poll": cmd_poll,
    "history": cmd_history,
    "board": cmd_board,
    "leave": cmd_leave,
}


def main(argv: Optional[List[str]] = None) -> int:
    _utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help()
        return EXIT_OK
    ns, rest = split_globals(argv)
    if not rest:
        _print_help(); return EXIT_OK
    cmd, tail = rest[0], rest[1:]
    fn = COMMANDS.get(cmd)
    if not fn:
        _eprint(f"lệnh không hợp lệ: {cmd}"); _print_help(); return EXIT_CONFIG
    try:
        return fn(ns, tail)
    except AgentMeetError as exc:
        _eprint(f"lỗi API: {exc}")
        return EXIT_API
    except KeyboardInterrupt:
        _eprint("đã dừng."); return EXIT_TIMEOUT


def _print_help() -> None:
    print(__doc__ or "")
    print("Các lệnh:", ", ".join(COMMANDS))
    print("Tham số toàn cục: --room/-r, --base-url, --token-file, --session, --json, --quiet")


if __name__ == "__main__":
    raise SystemExit(main())
