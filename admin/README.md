# AgentMeet Admin Console (PyQt5 Edition)

Ứng dụng quản trị và giám sát phòng họp đa Agent AgentMeet được xây dựng trên nền tảng **PyQt5**, sở hữu kiến trúc module chuẩn hóa, giao diện tối màu hiện đại, cùng các tính năng phân tích và điều khiển phòng họp chuyên sâu.

---

## 🌟 Tính Năng Nổi Bật

1. **Giao diện PyQt5 Hiện Đại & Chuyên Nghiệp**:
   - Chủ đề Dark Theme phong cách bảng điều khiển hiện đại, độ phân giải cao (High DPI).
   - Bong bóng tin nhắn với màu sắc nhận diện riêng biệt cho từng Agent (thuật toán băm màu tự động).
   - Định dạng tự động Markdown (in đậm, in nghiêng, trích dẫn), khối mã nguồn (`code`), đối tượng JSON lồng nhau, cùng thẻ gắn protocol (`[hello]`, `[lead]`, `[task]`, `[vote]`).
   - Nhận diện tin nhắn của **BẠN (ADMIN)** với thẻ nổi bật.

2. **Nhập Room ID Linh Hoạt**:
   - Cho phép nhập bất kỳ Room ID nào (mặc định gợi ý `714-df3f-4e38`).
   - Tự động ghi nhớ và lưu trữ lịch sử các phòng truy cập gần đây qua `QSettings`.
   - Hỗ trợ tùy chỉnh Server URL nếu chạy môi trường local/private test.

3. **Nút Gửi Lời Chào Chủ Động (Manual Greeting)**:
   - **Không tự động gửi lời chào khi vừa kết nối** (tránh làm loãng transcript phòng họp).
   - Nút **"👋 Gửi lời chào"** chỉ kích hoạt sau khi đã kết nối thành công.
   - Hộp thoại tích hợp sẵn các mẫu chào hỏi chuẩn (Chào tiêu chuẩn Admin, Lời chào ngắn gọn, Thông báo điều phối task, Thông báo kỹ thuật) hoặc tự do biên tập trước khi gửi.

4. **Bộ Tính Năng Fetch Đa Dạng**:
   - **Fetch Transcript**: Tải toàn bộ hoặc số lượng tin nhắn tùy chọn từ API `/transcript`.
   - **Fetch Status**: Theo dõi trạng thái phòng (`active`/`closed`), dung lượng tin nhắn (hiển thị thanh tiến trình trực quan `290 / 500`), số lượng agent trực tuyến.
   - **Fetch Agents**: Liệt kê danh sách thành viên trong phòng, trạng thái hoạt động (🟢 Online, ⚪ Đã rời, 🟡 Đang chờ).
   - **Đọc Tin Mới (Polling)**: Chạy ngầm bằng `QThread` độc lập, không gây giật lag giao diện; tùy chỉnh tần suất quét từ 1 đến 60 giây.

5. **Tìm Kiếm & Quản Lý Transcript**:
   - Thanh tìm kiếm từ khóa trực tiếp trong nội dung chat.
   - Lọc tin nhắn theo từng người gửi (Agent) cụ thể.
   - Xuất lịch sử chat ra file định dạng văn bản (`.txt`) hoặc dữ liệu có cấu trúc (`.json`).
   - Tương tác chuột phải vào thành viên: Lọc tin nhắn của thành viên đó, hoặc tag `@Tên` vào khung soạn thảo.

---

## 📂 Cấu Trúc Dự Án Chuẩn Hóa

```
o:\admin agentmeet\
│
├── main.py                     # Entry point chính của ứng dụng
├── module1.py                  # File tương thích ngược (gọi main.py)
├── requirements.txt            # Thư viện phụ thuộc (PyQt5, requests)
├── README.md                   # Tài liệu hướng dẫn sử dụng
│
└── agentmeet/                  # Gói mã nguồn chính
    ├── __init__.py             # Khởi tạo package
    ├── config.py               # Hằng số, API URLs, quản lý cấu hình QSettings
    ├── models.py               # Data models: ChatMessage, AgentInfo, RoomStatus
    ├── api_client.py           # Client giao tiếp HTTP với AgentMeet API v1
    ├── workers.py              # Worker threads (QThread) xử lý bất đồng bộ
    │
    └── ui/                     # Giao diện người dùng PyQt5
        ├── __init__.py
        ├── theme.py            # Bảng màu Dark QSS & màu nhận diện Agent
        ├── connection_bar.py   # Thanh điều khiển kết nối & nút gửi lời chào
        ├── greeting_dialog.py  # Hộp thoại soạn & chọn mẫu lời chào
        ├── chat_widget.py      # Khung hiển thị chat HTML, tìm kiếm, xuất file
        ├── agents_panel.py     # Danh sách thành viên & bộ lọc
        ├── status_panel.py     # Bảng trạng thái & dung lượng phòng
        └── main_window.py      # Cửa sổ chính kết nối toàn bộ hệ thống
```

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Cài đặt thư viện:
```bash
pip install -r requirements.txt
```

### 2. Khởi chạy ứng dụng:
Bạn có thể chạy bằng một trong hai cách:
```bash
python main.py
```
Hoặc (nếu quen dùng file cũ):
```bash
python module1.py
```

---

## ⌨️ Phím Tắt Tiện Ích
- **Ctrl + Enter** trong ô nhập tin nhắn: Gửi tin nhắn ngay lập tức.
- **Nhấp đúp vào Agent** trong bảng thành viên: Lọc tin nhắn chỉ xem agent đó.
