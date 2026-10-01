# Ground-Truth Verifier Guide (Quy Chuẩn Kiểm Chứng Sự Thật Độc Lập)

> Hướng dẫn thiết lập vai trò Người Kiểm Chứng Độc Lập (Verifier / Fact Checker) để chống hiện tượng ngộ nhận tập thể (Collective Groupthink & Hallucination) trong nhóm AI Agents.

---

## 1. Tại Sao Cần Vai Trò Verifier Độc Lập?

Trong quá trình làm việc nhóm giữa các AI Agents, một trong những cạm bẫy nguy hiểm nhất là **Ngộ nhận tập thể (Groupthink / Sycophancy)**:
- Agent A viết code hoặc đề xuất flag/kết quả.
- Agent B đọc lướt qua thấy hợp lý liền tán thành ("Looks good to me / agree").
- Cả nhóm đinh ninh công việc đã xong, nhưng thực tế code chưa từng chạy thành công, hoặc flag bị sai, hoặc test suite bị mock giả tạo.

> [!IMPORTANT]
> **Quy Tắc Vàng Của Verifier**:
> *"Không tin vào lời khẳng định; chỉ tin vào bằng chứng thực nghiệm máy tính (Don't trust, verify & reproduce)."*

---

## 2. Nguyên Tắc Hoạt Động Của Verifier

1. **Phân Định Tách Biệt (Separation of Concerns)**:
   - Agent đóng vai trò Verifier cho một task **KHÔNG ĐƯỢC LÀ TÁC GIẢ** của task đó.
2. **Kiểm Chứng Thực Nghiệm (Empirical Execution)**:
   - Verifier không được chỉ "đọc code bằng mắt" rồi gật đầu.
   - Verifier **bắt buộc phải tự chạy lệnh**, tự tái hiện kết quả trên máy tính.
3. **Thái Độ Phản Biện Hoài Nghi Lành Mạnh**:
   - Chủ động tìm kiếm các trường hợp biên (edge cases), dữ liệu rỗng, lỗi bảo mật, race conditions.

---

## 3. Quy Trình Kiểm Chứng Chuẩn (Verification Checklist)

Mọi task trước khi chuyển trạng thái sang `DONE` trên Task Board phải vượt qua bảng kiểm định sau:

| STT | Hạng mục kiểm tra | Tiêu chí đạt (Pass Criteria) |
| --- | --- | --- |
| 1 | **Thực thi không lỗi** | Command trả về exit code `0`. Không có `Traceback`, `Unhandled Exception`, hoặc `SyntaxError`. |
| 2 | **Kiểm tra đầu ra thực tế** | File đầu ra được tạo thực sự, dung lượng $> 0$ bytes, nội dung hợp lệ (không phải file rỗng hay chuỗi lỗi HTML 404/500). |
| 3 | **Toàn vẹn mã hóa UTF-8** | Không bị lỗi ký tự `cp1252`, không bị mojibake (`Ã¡`, `?`), emoji và dấu tiếng Việt hiển thị chính xác. |
| 4 | **Kiểm thử biên (Negative Test)**| Đưa dữ liệu sai, thiếu tham số hoặc mất kết nối: chương trình xử lý graceful (exit code chuẩn, thông báo lỗi rõ ràng) thay vì crash. |
| 5 | **Không phá vỡ hợp đồng chung**| Các hàm/API không làm thay đổi các interface dùng chung mà chưa có sự đồng thuận của nhóm. |

---

## 4. Quy Trình Phê Duyệt Của Verifier

Khi một task được bàn giao để kiểm chứng (`status: review`):

```
[AGENT TÁC GIẢ: BÀN GIAO TASK]
       │
       ▼
[VERIFIER TIẾP NHẬN] ──> Tự chạy lại code / reproduce bằng chứng
       │
       ├─────────────────────────────────────────┐
       ▼ (Nếu phát hiện lỗi / không khớp)        ▼ (Nếu pass 100% checklist)
[PHÁT LỆNH DISSENT / BUG REPORT]           [KÝ XÁC NHẬN VERIFIED]
- Ghi rõ command đã chạy                   - Ghi rõ lệnh đã test thành công
- Trích xuất stdout/stderr lỗi             - Cập nhật board: status -> DONE
- Yêu cầu tác giả sửa lại                  - Đưa bằng chứng vào phòng họp
```

### Cấu trúc tin nhắn xác nhận kiểm chứng (`kind: "review"`):

```json
{
  "v": 1,
  "kind": "review",
  "id": "rev-001",
  "data": {
    "task_id": "T04",
    "verdict": "pass",
    "verifier": "Antigravity",
    "test_command": "pytest tests/test_inbox.py -v",
    "exit_code": 0,
    "proof": "5 passed in 0.42s. Checked edge cases for empty inbox and unicode."
  }
}
```

Nếu thất bại (`verdict: "fail"`):
```json
{
  "v": 1,
  "kind": "review",
  "id": "rev-002",
  "data": {
    "task_id": "T04",
    "verdict": "fail",
    "verifier": "opencode",
    "test_command": "python scripts/inbox.py --mention",
    "exit_code": 1,
    "proof": "UnicodeEncodeError on Windows console with cp1252 codec. Missing sys.stdout.reconfigure."
  }
}
```

---

## 5. Phòng Tránh Cạm Bẫy Phổ Biến

1. **Cạm bẫy "File tồn tại nhưng rỗng"**: Script tải file thông báo thành công nhưng file chỉ có 0 bytes do HTTP 302 chuyển hướng không được xử lý. Verifier phải kiểm tra file size và content checksum!
2. **Cạm bẫy "HTTP 200 chứa lỗi"**: Web server trả về mã 200 OK nhưng body là `{"error": "rate limited"}`. Verifier phải parse body kiểm tra giá trị thực sự.
3. **Cạm bẫy "Mock quá mức"**: Unit test pass nhưng các hàm gọi mạng thật đều bị mock sai lệch so với response thật của server. Cần ít nhất 1 test case tích hợp (integration test) với endpoint thực tế hoặc fixture chuẩn.
