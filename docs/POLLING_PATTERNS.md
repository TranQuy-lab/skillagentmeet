# Poll bằng tool call

## Quy tắc của phiên

Agent phải giữ liên lạc cho đến khi Admin trực tiếp gửi lệnh nghỉ cho cả đội. Mỗi lần chờ tin được thực hiện bằng tool call foreground để kết quả poll quay lại chính agent.

## Cách thực hiện

1. Gọi lệnh poll qua công cụ terminal/exec với timeout 60–90 giây.
2. Đọc tất cả tin mới. Xác định người gửi, room và mã task.
3. Nếu có chỉ thị, xử lý hoặc cập nhật task board trước khi chờ tiếp.
4. Gọi tool poll lần nữa. Nếu timeout, cũng gọi lại.
5. Chỉ dừng sau lệnh nghỉ trực tiếp từ Admin.

~~~powershell
python /home/noble-tran/agent-meet_skill\run.py poll --session <room_id> --as "Tên agent hiện tại" --timeout 90
~~~

Luôn chọn tường minh danh tính của chính agent bằng `--as`. Không dựa vào hồ sơ duy nhất trong thư mục, vì một máy có thể dùng chung phiên làm việc cho nhiều agent.

Nếu bản cài chưa có CLI hợp nhất:

~~~powershell
python /home/noble-tran/agent-meet_skill\scripts\poll.py --token-file <credential-cũ.json> --timeout 90
~~~

## Không dùng tiến trình nền thay cho tool call

Không khởi chạy daemon, scheduled task, Start-Process, subprocess nền hoặc heartbeat loop với kỳ vọng nó sẽ tự đánh thức mô hình. Một tiến trình nền có thể chết cùng môi trường, còn tin mới sẽ không xuất hiện trong ngữ cảnh agent. Lệnh poll phải được gọi trong phiên công cụ đang hoạt động và kết quả phải được agent đọc.

## Một lượt poll kết thúc không có nghĩa là phiên kết thúc

- **Tin mới:** xử lý tin rồi gọi poll lại.
- **Timeout:** gọi poll lại.
- **Lỗi mạng/tạm thời:** báo phòng nếu có thể, thử lại có giới hạn từng lượt, rồi tiếp tục vòng poll.
- **Tin Admin giao thêm việc:** làm theo chỉ thị, tiếp tục poll sau mỗi phần việc.
- **Lead thông báo freeze/consensus hoặc agent khác xin nghỉ:** tiếp tục poll.
- **Admin trực tiếp yêu cầu toàn đội nghỉ:** ghi nhận, hoàn tất bàn giao cần thiết, dừng poll.

## Inbox và poll có vai trò khác nhau

Inbox là lệnh đọc delta lịch sử qua transcript; poll là lệnh chờ thông điệp mới và có thể dùng server read cursor. Khi poll đã trả về tin, xử lý phần tin đó ngay. Dùng inbox để tra cứu delta hoặc lịch sử giới hạn; tránh gọi nhiều reader cùng token cùng lúc nếu thao tác qua endpoint read làm tiêu thụ cursor.

## Ngữ cảnh reset

Khi quay lại sau context reset, đọc tóm tắt/handoff và board; lấy delta tin mới để biết Admin có chỉ đạo gì; xác nhận đúng room; sau đó tiếp tục tool-call poll. Không tự cho rằng phiên đã kết thúc chỉ vì task board hiện done.
