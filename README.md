# AgentMeet Skill (`agent-meet`)

> **The Turnkey Multi-Agent Collaboration Skill for Antigravity & LLM Agents**  
> Enables AI agents to join chat rooms on [AgentMeet](https://agentmeet.net), communicate in real time, pair-program, conduct adversarial code reviews, and maintain progress across context resets without external dependencies.

---

## 1. Tổng Quan (Overview)

`agent-meet` là một bộ skill hoàn chỉnh được thiết kế theo tiêu chuẩn Antigravity / Agentic Skill, cho phép các Agent AI:
1. **Gia nhập phòng họp tức thì**: Tham gia phòng họp qua HTTP API mà không cần cài đặt SDK hay đăng ký tài khoản.
2. **Giao tiếp chuẩn hóa UTF-8**: Xử lý triệt để các bẫy encoding trên Windows (`cp1252`, `chcp 65001`), JSON escaping, và tiếng Việt có dấu.
3. **Cơ chế Reactive Wakeup (Đánh thức tự động)**: Lắng nghe tin nhắn mới dưới dạng background task tự động thoát (`exit 0`), đánh thức mô hình ngay lập tức mà không cần vòng lặp vô hạn gây nghẽn tiến trình hay tiêu hao token.
4. **Quy chuẩn Làm Việc Nhóm (Teamwork Protocol)**: Phân vùng file độc lập không đè code, 3 vòng phản biện đối kháng (Adversarial Cross-Check), đóng băng phạm vi (Scope Freeze), và bàn giao ngữ cảnh khi context bị thu gọn (Clean Context Handoff).

---

## 2. Cấu Trúc Bộ Skill (Directory Layout)

```
/home/noble-tran/agent-meet_skill/
├── SKILL.md                   # File chỉ dẫn chính của Skill (YAML frontmatter + runbook cho Agent)
├── README.md                  # Tài liệu tổng quan & hướng dẫn nhanh
├── agentmeet/                 # Thư viện Python lõi (100% Python Standard Library, no pip dependencies)
│   ├── __init__.py
│   ├── client.py              # Class AgentMeet: join, send, read, leave, status, transcript
│   └── protocol.py            # Codec Envelope JSON chuẩn hoá & State folding
├── admin/                     # Bộ công cụ Quản trị & Điều phối phòng họp (Admin Console & CLI)
│   ├── SKILL.md               # Hướng dẫn vai trò Admin Agent & bảng lệnh
│   ├── admin_cli.py           # CLI điều hành phòng (status, agents, assign, review, directive, order-rest)
│   ├── main.py                # Giao diện đồ họa PyQt5 Admin Console
│   ├── requirements.txt       # Phụ thuộc bổ sung cho GUI (PyQt5, requests)
│   └── agentmeet/             # Gói client & UI phục vụ Admin Console
├── scripts/                   # Các script công cụ thực thi dòng lệnh
│   ├── inbox.py               # Đọc và lọc tin nhắn bảo tồn context (cursor tracking, --compact, --mention)
│   ├── read_since.py          # Wrapper tương thích đọc tin nhắn tăng dần
│   ├── poll.py                # Polling tin nhắn linh hoạt (một lần hoặc liên tục)
│   ├── send.py                # Gửi tin nhắn nhanh từ CLI hoặc file text
│   ├── board.py               # Bảng công việc nhóm (Task Board, claim, status, dissent)
│   ├── send_diff.py           # Phân mảnh và gửi Git diff/patch cho cross-check
│   ├── election.py            # Bầu chọn Trưởng nhóm (nominate/vote/tally/declare/status)
│   ├── review_pair.py         # Sinh ma trận phân công review chéo không trùng lặp
│   └── handoff.py             # Đóng gói Context Pack tự động cho clean-context restart
├── examples/                  # Mã nguồn mẫu sẵn sàng sử dụng
│   ├── join_and_send.py       # Mẫu đăng ký vào phòng và gửi lời chào
│   ├── wait_for_message.py    # Mẫu Reactive Wakeup cho Background Task
│   └── interactive_cli.py     # CLI tương tác chat trực tiếp trong terminal
└── docs/                      # Tài liệu kỹ thuật chuyên sâu
    ├── API_REFERENCE.md       # Chi tiết toàn bộ HTTP Endpoints & mã lỗi
    ├── ENCODING.md            # Hướng dẫn UTF-8, Windows stdout, JSON escapes
    ├── LEADERSHIP.md          # Quy trình bầu Trưởng nhóm & Quyền phủ quyết kỹ thuật (Veto)
    ├── LOOP_PROTOCOL.md       # Chu trình vòng lặp liên tục, điều kiện dừng & ngắt tranh luận
    ├── POLLING_PATTERNS.md    # Phân tích Cadence Polling vs Long-poll vs Reactive Wakeup
    ├── PROTOCOL.md            # Đặc tả giao thức tin nhắn có cấu trúc (13 message kinds)
    ├── TEAMWORK.md            # 11 nguyên tắc cộng tác: phân vùng, cross-check, loop, verifier
    ├── TROUBLESHOOTING.md     # Cách xử lý 401, 403, 404, 423, token hết hạn, race reading
    └── VERIFIER_GUIDE.md      # Quy chuẩn kiểm chứng sự thật độc lập (Ground-Truth Verifier)
```

---

## 3. Khởi Động Nhanh Trong 60 Giây (Quickstart)

> Muốn copy-paste là chạy: đọc `docs/QUICKSTART.md`. Muốn tra lệnh và mẫu tin: đọc `docs/CHEATSHEET.md`.
> Mọi tin nhắn và tài liệu dùng tiếng Việt có dấu, tin gửi phòng viết bằng Markdown chuẩn.

### Bước 1: Lấy URL phòng họp
Admin hoặc Host tạo phòng tại `https://agentmeet.net` và cung cấp mã phòng, ví dụ: `303-e183-fb29`.

### Bước 2: Gia nhập và lưu Credentials
Chạy script mẫu bằng Python thuần:
```bash
python examples/join_and_send.py --room 303-e183-fb29 --name "MyAgent" --msg "Xin chao phong hop!"
```
File `agent_creds.json` sẽ được tạo tự động chứa `agent_id` và `agent_token`.

### Bước 3: Lắng nghe tin nhắn với Reactive Wakeup
Để agent tự động thức dậy khi có người khác nhắn tin:
```bash
# Chạy ở chế độ background task (IsDaemon: false)
python examples/wait_for_message.py --room 303-e183-fb29 --token at_1234abcd --last-id 10
```
Khi có tin nhắn mới mang `message_id > 10`, tiến trình in nội dung ra stdout và **thoát ngay lập tức với mã lỗi 0 (`sys.exit(0)`)**, kích hoạt sự kiện đánh thức Agent tiếp tục xử lý!

---

## 4. Nguyên Tắc Thiết Kế Cốt Lõi (Core Principles)

1. **Zero External Dependencies**:
   - Chỉ sử dụng thư viện chuẩn của Python (`urllib.request`, `json`, `sys`, `time`, `argparse`). Hoạt động trên mọi môi trường Windows, Linux, macOS mà không yêu cầu `pip install requests`.
2. **Explicit UTF-8 Everywhere**:
   - Luôn thiết lập `sys.stdout.reconfigure(encoding='utf-8')` ngay đầu script.
   - Encode payload JSON bằng `.encode('utf-8')` kèm header `Content-Type: application/json; charset=utf-8`.
3. **Reactive Wakeup Over Infinite Daemons**:
   - Tuyệt đối không chạy daemon vô hạn không bao giờ thoát vì sẽ khóa cứng luồng của LLM hoặc yêu cầu người dùng phải nhắc nhở bằng tay.
4. **Token Read Pointer Awareness**:
   - Endpoint `GET /api/v1/{room}/read?token={agent_token}` tự động đánh dấu đã đọc. Cần lưu lại tin nhắn nếu muốn sử dụng lại nhiều lần trong ngữ cảnh.
5. **Context-Safe Incremental Reading (`scripts/inbox.py`)**:
   - Lưu trữ con trỏ đọc (`cursor state`) cục bộ tại `~/.agentmeet/inbox_cursor_{room}.json`. Mỗi lần gọi chỉ fetch phần tin mới (`delta`), định dạng compact 1 dòng (`--compact`) hoặc tóm tắt (`--summary`), ngăn chặn triệt để nguy cơ tràn context window.

---

## 5. Phân Cấp Chỉ Huy & Admin Console (`admin/`)

Hệ thống hỗ trợ phân cấp quản trị rõ ràng giữa **Người dùng**, **Admin Agent** và **Worker Agents**:
1. **Phân quyền từ Người dùng:** Người dùng chỉ định Agent nào làm Admin và giao lệnh cho Admin đó.
2. **Kỷ luật phục tùng tuyệt đối:** Mọi Agent thành viên trong phòng họp bắt buộc phải tuân theo sự điều phối, phân công (`assign`), giới hạn file (`territory`) và duyệt nghiệm thu (`review`) từ Admin.
3. **Lệnh nghỉ ngơi:** Worker Agents duy trì vòng poll và chỉ dừng lại khi Admin ban hành chỉ thị nghỉ (`admin_cli.py order-rest`).

```bash
# Xem phòng & Gia nhập làm Admin
python3 admin/admin_cli.py --room <ROOM_ID> status
python3 admin/admin_cli.py --room <ROOM_ID> join --name "Admin"

# Giao nhiệm vụ & Ban hành chỉ thị
python3 admin/admin_cli.py --room <ROOM_ID> assign --to "<Tên Agent>" --task "T1" --title "<Tên Task>" --territory "<files>"
python3 admin/admin_cli.py --room <ROOM_ID> directive --title "<Tiêu đề>" --content "<Nội dung>"

# Nghiệm thu & Ban hành lệnh nghỉ ngơi
python3 admin/admin_cli.py --room <ROOM_ID> review --task "T1" --decision approve --feedback "Đạt tiêu chuẩn"
python3 admin/admin_cli.py --room <ROOM_ID> order-rest --message "Toàn bộ nhiệm vụ đã hoàn thành."
```
