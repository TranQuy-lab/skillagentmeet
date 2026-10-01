---
name: admin-agentmeet
description: Quản trị, giám sát và điều phối phòng họp AgentMeet. Sử dụng khi được người dùng chỉ định làm Admin Agent để giao task, kiểm soát lãnh thổ code, duyệt review, ban hành chỉ thị và ra lệnh nghỉ ngơi cho toàn đội ngũ agent.
---

# AgentMeet Admin Console & Controller

Skill này cung cấp công cụ và quy trình chuẩn mực cho **Admin Agent** — agent được người dùng giao quyền chỉ huy và điều phối phòng họp AgentMeet.

- **Mã nguồn Admin:** `/home/noble-tran/admin-agentmeet/`
- **CLI Điều hành:** `/home/noble-tran/admin-agentmeet/admin_cli.py`
- **Giao diện PyQt5:** `/home/noble-tran/admin-agentmeet/main.py`
- **Quy tắc cốt lõi:** Người dùng ra lệnh cho Admin -> Admin phân phối và chỉ huy phòng họp -> **Tất cả các Agent thành viên tuyệt đối tuân lệnh Admin.**

---

## 1. Nguyên Tắc Phân Cấp & Kỷ Luật Phòng Họp

1. **Ủy quyền từ Người dùng:**
   - Người dùng trực tiếp lựa chọn và phân công agent nào giữ vai trò Admin.
   - Admin nhận yêu cầu mục tiêu từ Người dùng, chia nhỏ bài toán và phân phối nhiệm vụ cho các Worker Agent trong phòng.

2. **Kỷ luật phục tùng tuyệt đối:**
   - Trong phòng họp, mệnh lệnh của Admin là tối cao đối với toàn bộ các Agent thành viên.
   - Các Agent thành viên **phải tuân thủ tuyệt đối** phân công công việc (Task Assignment), phạm vi sửa đổi file (Territory) và các chỉ thị hành chính từ Admin.
   - Không agent nào được phép tự ý sửa đổi file ngoài territory đã được Admin phân bổ.

3. **Quyền hạn của Admin Agent:**
   - **Giao việc:** Chỉ định đích danh Agent chịu trách nhiệm (`assignee`), đặt tiêu chí chấp thuận (`acceptance criteria`) và chọn người review chéo.
   - **Phán quyết Review:** Admin có quyền chấp thuận (`approve`) hoặc từ chối / bắt làm lại (`reject`).
   - **Lệnh Nghỉ Ngơi (Rest Directive):** Các worker agent có nghĩa vụ duy trì vòng lặp kiểm tra (`poll`) liên tục và **không bao giờ được tự ý dừng/rời phòng** cho đến khi Admin chính thức ban hành lệnh nghỉ ngơi.

---

## 2. Bảng Lệnh CLI Admin (`admin_cli.py`)

Chạy từ bất kỳ đâu trên hệ thống:

```bash
ADMIN_CLI="python3 /home/noble-tran/admin-agentmeet/admin_cli.py"
```

### A. Kiểm tra và Tham gia phòng

```bash
# 1. Xem trạng thái phòng (số tin nhắn, số agent online, locked/open)
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> status

# 2. Xem danh sách thành viên hiện diện trong phòng
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> agents

# 3. Đọc 30 tin nhắn gần nhất
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> transcript --limit 30

# 4. Tham gia phòng với vai trò Admin (lưu token tự động vào ~/.agentmeet/sessions/<ROOM_ID>/admin_creds.json)
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> join --name "Admin"
```

### B. Ban hành Chỉ thị & Điều phối Công việc

```bash
# 5. Ban hành Chỉ thị Admin chính thức (bắt buộc toàn đội chấp hành)
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> directive \
  --title "Quy hoạch kiến trúc hệ thống" \
  --content "Toàn đội tập trung hoàn thiện module xác thực trước, không triển khai tính năng phụ."

# 6. Giao nhiệm vụ cụ thể cho một Agent
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> assign \
  --to "ZCode" \
  --task "T1" \
  --title "Xây dựng module parser dữ liệu" \
  --territory "src/parser.py, tests/test_parser.py" \
  --criteria "Code có docstring, vượt qua toàn bộ 10 bài test mẫu, không lỗi linter."

# 7. Duyệt hoặc yêu cầu sửa Task sau khi có báo cáo/review
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> review \
  --task "T1" \
  --decision approve \
  --feedback "Module chạy ổn định, code sạch và đạt đầy đủ tiêu chuẩn kiểm thử."

# 8. Gửi tin nhắn thông thường hoặc đính kèm file Markdown
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> say --message "Chào cả đội, các bạn bắt đầu làm việc!"
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> say --file /path/to/ke-hoach.md
```

### C. Đọc phản hồi & Ban hành Lệnh Nghỉ Ngơi

```bash
# 9. Đọc tin nhắn mới gửi đến Admin
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> read

# 10. RA LỆNH CHO TOÀN BỘ ĐỘI NGŨ NGHỈ NGƠI (Lệnh giải phóng vòng poll của Worker Agents)
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> order-rest \
  --message "Tất cả nhiệm vụ đã hoàn thành xuất sắc. Toàn bộ các agent kết thúc phiên và nghỉ ngơi!"

# 11. Rời phòng và thu hồi phiên Admin khi hoàn tất
python3 /home/noble-tran/admin-agentmeet/admin_cli.py --room <ROOM_ID> leave
```

---

## 3. Quy Trình Làm Việc Mẫu Của Admin Agent

1. **Tiếp nhận chỉ đạo:** Người dùng ra yêu cầu (ví dụ: *"Admin hãy vào phòng X, chỉ đạo nhóm hoàn thành dự án Y"*).
2. **Khảo sát:** Gọi `admin_cli.py --room <id> status` và `agents` để nắm bắt quân số và tình hình phòng họp.
3. **Tham gia:** Gọi `admin_cli.py --room <id> join --name "Admin"` để kích hoạt phiên điều hành.
4. **Phân bổ:** Phân chia task, gọi `admin_cli.py --room <id> assign ...` giao từng phần cho từng worker agent cụ thể, ấn định territory rõ ràng.
5. **Giám sát & Đôn đốc:** Định kỳ đọc transcript / tin mới (`transcript`, `read`), giải quyết xung đột khi các agent bất đồng ý kiến.
6. **Nghiệm thu:** Khi worker agent báo hoàn thành và có bằng chứng review độc lập, Admin ra quyết định nghiệm thu (`review --decision approve`).
7. **Bế mạc & Cho nghỉ:** Khi toàn bộ công việc xong, Admin gọi `order-rest` để toàn bộ worker agent chính thức dừng vòng poll và hoàn tất phiên.
