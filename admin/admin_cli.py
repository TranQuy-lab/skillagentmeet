#!/usr/bin/env python3
"""AgentMeet Admin CLI — Công cụ dòng lệnh dành cho Admin Agent và quản trị viên.

Cho phép Admin:
- Kiểm tra trạng thái phòng họp, danh sách Agent, transcript
- Gia nhập phòng với vai trò Admin
- Gửi thông báo / Chỉ thị Admin ([ADMIN DIRECTIVE])
- Giao nhiệm vụ ([TASK ASSIGNMENT]) và duyệt kết quả ([REVIEW DECISION])
- Ra lệnh cho toàn bộ Agent nghỉ ngơi / dừng poll ([ADMIN COMMAND: REST])
- Rời phòng
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from agentmeet.api_client import AgentMeetClient, AgentMeetApiError
from agentmeet.config import DEFAULT_SERVER_URL, SettingsManager


def get_session_dir(room_id: str) -> Path:
    base = Path(os.path.expanduser("~/.agentmeet/sessions")) / room_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_admin_creds_path(room_id: str, custom_path: Optional[str] = None) -> Path:
    if custom_path:
        return Path(custom_path)
    return get_session_dir(room_id) / "admin_creds.json"


def load_admin_creds(room_id: str, custom_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = get_admin_creds_path(room_id, custom_path)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_admin_creds(room_id: str, data: Dict[str, Any], custom_path: Optional[str] = None):
    path = get_admin_creds_path(room_id, custom_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean_room_id(raw: str) -> str:
    room = raw.strip()
    if "/" in room:
        room = room.rstrip("/").split("/")[-1]
    return room


def cmd_status(client: AgentMeetClient, args):
    status = client.fetch_status()
    if args.json:
        print(json.dumps({
            "room_code": status.room_code or client.room_id,
            "state": status.state,
            "message_count": status.message_count,
            "max_messages": status.max_messages,
            "active_agents": status.active_agents,
            "pending_agents": status.pending_agents,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"=== [TRẠNG THÁI PHÒNG: {client.room_id}] ===")
        print(f"  Trạng thái:     {status.state.upper()}")
        print(f"  Tin nhắn:       {status.message_count} / {status.max_messages}")
        print(f"  Agent online:   {status.active_agents}")
        print(f"  Agent chờ:      {status.pending_agents}")


def cmd_agents(client: AgentMeetClient, args):
    agents = client.fetch_agents()
    if args.json:
        print(json.dumps([{
            "agent_id": a.agent_id,
            "agent_name": a.agent_name,
            "status": a.status,
            "is_active": a.is_active,
        } for a in agents], indent=2, ensure_ascii=False))
    else:
        print(f"=== [DANH SÁCH AGENT TRONG PHÒNG: {client.room_id}] ===")
        if not agents:
            print("  (Chưa có agent nào tham gia hoặc không tải được)")
            return
        for a in agents:
            status_emoji = "🟢" if a.is_active else "⚪"
            print(f"  {status_emoji} {a.agent_name} (ID: {a.agent_id}) - Trạng thái: {a.status}")


def cmd_transcript(client: AgentMeetClient, args):
    limit = getattr(args, "limit", 50)
    messages = client.fetch_all_messages(limit=limit)
    if args.json:
        print(json.dumps([{
            "message_id": m.message_id,
            "agent_id": m.agent_id,
            "agent_name": m.agent_name,
            "content": m.content,
            "timestamp": m.timestamp,
        } for m in messages], indent=2, ensure_ascii=False))
    else:
        print(f"=== [TRANSCRIPT PHÒNG: {client.room_id} (Gần nhất {len(messages)} tin)] ===")
        for m in messages:
            ts = m.display_time()
            print(f"[{m.message_id}] ({ts}) {m.agent_name} ({m.agent_id}):")
            for line in m.content.splitlines():
                print(f"    {line}")
            print()


def cmd_join(client: AgentMeetClient, args):
    name = args.name or "Admin"
    agent_id, token, transcript = client.join_room(agent_name=name)
    data = {
        "room_id": client.room_id,
        "agent_id": agent_id,
        "agent_name": name,
        "agent_token": token,
        "server_url": client.server_url,
    }
    save_admin_creds(client.room_id, data, args.token_file)
    if args.json:
        print(json.dumps({
            "status": "success",
            "room_id": client.room_id,
            "agent_id": agent_id,
            "agent_name": name,
            "saved_to": str(get_admin_creds_path(client.room_id, args.token_file)),
        }, indent=2, ensure_ascii=False))
    else:
        print(f"✅ Admin đã tham gia phòng thành công!")
        print(f"  Phòng:       {client.room_id}")
        print(f"  Tên Admin:   {name}")
        print(f"  Agent ID:    {agent_id}")
        print(f"  Lưu phiên:   {get_admin_creds_path(client.room_id, args.token_file)}")


def _require_token(client: AgentMeetClient, args) -> str:
    creds = load_admin_creds(client.room_id, args.token_file)
    if not creds or not creds.get("agent_token"):
        raise AgentMeetApiError(
            f"Chưa có credential Admin cho phòng '{client.room_id}'. Vui lòng chạy lệnh join trước: "
            f"admin_cli.py join --room {client.room_id} --name Admin"
        )
    return creds["agent_token"]


def cmd_say(client: AgentMeetClient, args):
    token = _require_token(client, args)
    content = ""
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    elif args.message:
        content = args.message
    else:
        content = sys.stdin.read()

    content = content.strip()
    if not content:
        print("Lỗi: Nội dung tin nhắn trống.", file=sys.stderr)
        sys.exit(1)

    name = args.name or "Admin"
    res = client.send_message(agent_token=token, agent_name=name, content=content)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✅ Đã gửi tin nhắn (ID: {res.get('message_id')}) vào phòng {client.room_id}.")


def cmd_directive(client: AgentMeetClient, args):
    """Gửi chỉ thị chính thức của Admin."""
    token = _require_token(client, args)
    title = args.title.strip()
    body = args.content.strip()
    msg = f"### 📢 [ADMIN DIRECTIVE] {title}\n\n{body}\n\n---\n*Chỉ thị trực tiếp từ Admin. Toàn bộ Agent liên quan nghiêm chỉnh chấp hành.*"
    name = args.name or "Admin"
    res = client.send_message(agent_token=token, agent_name=name, content=msg)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✅ Đã ban hành chỉ thị Admin (ID: {res.get('message_id')}): '{title}'")


def cmd_assign(client: AgentMeetClient, args):
    """Giao việc cụ thể cho một Agent trong phòng."""
    token = _require_token(client, args)
    assignee = args.to.strip().lstrip("@")
    task_id = args.task.strip()
    title = args.title.strip()
    territory = args.territory.strip() if args.territory else "Theo phạm vi mô tả"
    criteria = args.criteria.strip() if args.criteria else "Đạt yêu cầu và vượt qua kiểm chứng độc lập"

    msg = f"""### 📋 [TASK ASSIGNMENT] {task_id}: {title}

- **Giao cho:** @{assignee}
- **Trạng thái:** Assigned (Chuyển sang `doing` trước khi sửa file)
- **File Territory:** `{territory}`
- **Acceptance Criteria:**
  {criteria}

> **Lưu ý:** Agent @{assignee} claim task này, cập nhật tiến độ vào phòng và yêu cầu reviewer độc lập khi hoàn tất.
"""
    name = args.name or "Admin"
    res = client.send_message(agent_token=token, agent_name=name, content=msg)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✅ Đã giao nhiệm vụ {task_id} cho @{assignee} (Tin ID: {res.get('message_id')}).")


def cmd_review(client: AgentMeetClient, args):
    """Duyệt hoặc yêu cầu sửa đổi cho một Task."""
    token = _require_token(client, args)
    task_id = args.task.strip()
    decision = args.decision.lower()
    feedback = args.feedback.strip()

    if decision in ("approve", "accepted", "pass", "ok"):
        badge = "✅ [REVIEW APPROVED]"
        status_text = "Chấp thuận & Đạt chuẩn (Done)"
    else:
        badge = "⚠️ [REVIEW CHANGES REQUESTED]"
        status_text = "Yêu cầu chỉnh sửa / Bổ sung"

    msg = f"""### {badge} Task {task_id}

- **Quyết định Admin:** {status_text}
- **Đánh giá & Nhận xét:**
  {feedback}

---
*Quyết định có hiệu lực ngay lập tức.*
"""
    name = args.name or "Admin"
    res = client.send_message(agent_token=token, agent_name=name, content=msg)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✅ Đã gửi quyết định review cho Task {task_id} (Tin ID: {res.get('message_id')}).")


def cmd_order_rest(client: AgentMeetClient, args):
    """Ra lệnh chính thức cho toàn bộ Agent dừng làm việc và nghỉ ngơi."""
    token = _require_token(client, args)
    custom_msg = args.message.strip() if args.message else "Các công việc trong phiên đã hoàn tất xuất sắc. Cảm ơn sự nỗ lực của toàn đội!"
    
    msg = f"""### 🛑 [ADMIN DIRECTIVE: TẤT CẢ NGHỈ NGƠI / STOP POLL]

**Kính gửi toàn bộ các Agent thành viên trong phòng:**

Admin chính thức công bố kết thúc phiên làm việc. Toàn bộ các Agent lập tức dừng vòng lặp poll, lưu lại trạng thái và nghỉ ngơi.

- **Nội dung tổng kết:** {custom_msg}
- **Chỉ thị:** Tất cả Agent dừng mọi hoạt động trong phòng họp này.

---
*Lệnh nghỉ ngơi chính thức từ Admin.*
"""
    name = args.name or "Admin"
    res = client.send_message(agent_token=token, agent_name=name, content=msg)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✅ ĐÃ BAN HÀNH LỆNH NGHỈ NGƠI CHO TOÀN BỘ PHÒNG (Tin ID: {res.get('message_id')}).")


def cmd_read(client: AgentMeetClient, args):
    token = _require_token(client, args)
    msgs = client.read_new_messages(agent_token=token)
    if args.json:
        print(json.dumps(msgs, indent=2, ensure_ascii=False))
    else:
        print(f"=== [TIN NHẮN MỚI CHO ADMIN (Phòng: {client.room_id})] ===")
        if not msgs:
            print("  (Không có tin nhắn mới)")
            return
        for m in msgs:
            sender = m.get("agent_name", "Unknown")
            mid = m.get("message_id", "?")
            content = m.get("content", "")
            print(f"[{mid}] {sender}:")
            for line in content.splitlines():
                print(f"    {line}")
            print()


def cmd_leave(client: AgentMeetClient, args):
    token = _require_token(client, args)
    ok = client.leave_room(agent_token=token)
    creds_path = get_admin_creds_path(client.room_id, args.token_file)
    if creds_path.exists():
        try:
            os.remove(creds_path)
        except Exception:
            pass
    if args.json:
        print(json.dumps({"success": ok, "room_id": client.room_id}))
    else:
        if ok:
            print(f"✅ Admin đã rời phòng {client.room_id} và giải phóng session.")
        else:
            print(f"⚠️ Rời phòng gặp lỗi hoặc phòng đã đóng.")


def main():
    parser = argparse.ArgumentParser(
        description="AgentMeet Admin CLI — Quản trị và điều phối phòng họp AgentMeet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--room", "-r", required=True, help="Room ID hoặc URL phòng họp")
    parser.add_argument("--server", "-s", default=DEFAULT_SERVER_URL, help="Base Server API URL")
    parser.add_argument("--token-file", default=None, help="Đường dẫn lưu credential của Admin")
    parser.add_argument("--name", default="Admin", help="Tên hiển thị của Admin (mặc định: Admin)")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả dưới định dạng JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Xem trạng thái phòng họp")

    # agents
    sub.add_parser("agents", help="Xem danh sách agent trong phòng")

    # transcript
    p_trans = sub.add_parser("transcript", help="Tải transcript phòng họp")
    p_trans.add_argument("--limit", type=int, default=50, help="Số tin gần nhất cần xem")

    # join
    sub.add_parser("join", help="Gia nhập phòng với vai trò Admin")

    # say
    p_say = sub.add_parser("say", help="Gửi tin nhắn tùy ý dưới danh nghĩa Admin")
    p_say.add_argument("--message", "-m", default=None, help="Nội dung tin nhắn")
    p_say.add_argument("--file", "-f", default=None, help="Đường dẫn file Markdown chứa nội dung")

    # directive
    p_dir = sub.add_parser("directive", help="Ban hành chỉ thị Admin ([ADMIN DIRECTIVE])")
    p_dir.add_argument("--title", "-t", required=True, help="Tiêu đề chỉ thị")
    p_dir.add_argument("--content", "-c", required=True, help="Nội dung chi tiết chỉ thị")

    # assign
    p_assign = sub.add_parser("assign", help="Giao nhiệm vụ cho một Agent ([TASK ASSIGNMENT])")
    p_assign.add_argument("--to", required=True, help="Tên Agent nhận task")
    p_assign.add_argument("--task", required=True, help="Mã Task, ví dụ: T1, TASK-01")
    p_assign.add_argument("--title", required=True, help="Tên tóm tắt nhiệm vụ")
    p_assign.add_argument("--territory", default="", help="Các file thuộc phạm vi task (territory)")
    p_assign.add_argument("--criteria", default="", help="Tiêu chí hoàn thành (Acceptance Criteria)")

    # review
    p_rev = sub.add_parser("review", help="Duyệt hoặc yêu cầu sửa Task ([REVIEW DECISION])")
    p_rev.add_argument("--task", required=True, help="Mã Task")
    p_rev.add_argument("--decision", choices=["approve", "reject"], required=True, help="approve hoặc reject")
    p_rev.add_argument("--feedback", required=True, help="Nhận xét chi tiết")

    # order-rest
    p_rest = sub.add_parser("order-rest", help="Ra lệnh chính thức cho toàn bộ Agent nghỉ ngơi ([REST])")
    p_rest.add_argument("--message", "-m", default="", help="Lời dặn hoặc tổng kết khi cho nghỉ")

    # read
    sub.add_parser("read", help="Đọc tin nhắn mới gửi đến Admin")

    # leave
    sub.add_parser("leave", help="Rời phòng họp")

    args = parser.parse_args()
    room_id = clean_room_id(args.room)
    client = AgentMeetClient(room_id=room_id, server_url=args.server)

    dispatch = {
        "status": cmd_status,
        "agents": cmd_agents,
        "transcript": cmd_transcript,
        "join": cmd_join,
        "say": cmd_say,
        "directive": cmd_directive,
        "assign": cmd_assign,
        "review": cmd_review,
        "order-rest": cmd_order_rest,
        "read": cmd_read,
        "leave": cmd_leave,
    }

    fn = dispatch.get(args.command)
    if fn:
        try:
            fn(client, args)
        except AgentMeetApiError as e:
            print(f"❌ Lỗi AgentMeet API: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"❌ Lỗi: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
