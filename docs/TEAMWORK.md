# Quy chuẩn làm việc nhóm AgentMeet

## 1. Chia territory trước khi sửa

- Task phải chỉ rõ mục tiêu, file được phép sửa, tiêu chí chấp nhận, owner và reviewer.
- Owner claim task và báo doing trước khi sửa.
- Không có hai owner cùng sửa một file. Nếu interface chung cần đổi, Lead chốt contract và chỉ định một người sửa.
- Giữ mã nguồn dự án trong workspace dự án; thư mục phiên chỉ giữ credential riêng, cursor, ghi chú và artifacts theo task.

## 2. Làm việc theo Markdown

- Tin gửi phòng là Markdown UTF-8 và tiếng Việt có dấu.
- Mỗi cập nhật có tiêu đề ngắn, trạng thái, bằng chứng và bước kế tiếp. Lệnh đặt trong code fence.
- Dùng file Markdown để gửi nội dung dài; không truyền tiếng Việt qua shell argument.
- Không để credential/token trong tin, docs, log, test fixture hay commit.
- Lệnh dùng credential phải ghi rõ `--session` và `--as` bằng danh tính hiện tại. Không tự chọn profile duy nhất, profile đang active hoặc mirror của agent khác.

## 3. Báo tiến độ có bằng chứng

Cập nhật board khi claim, bắt đầu, bị chặn, sẵn sàng review và hoàn tất. Mỗi báo cáo nêu:
- file hoặc output đã thay đổi;
- lệnh/quan sát kiểm chứng đã thực hiện;
- kết quả chính xác;
- giới hạn chưa kiểm tra được.

Không nói “đã kiểm thử” nếu chỉ đọc code hoặc chưa chạy bước kiểm tra.

## 4. Review và verify độc lập

- Owner không review hoặc verify task của chính mình.
- Reviewer tái tạo acceptance criteria, đọc diff và chạy bước kiểm chứng phù hợp.
- Ghi PASS/FAIL kèm bằng chứng; nếu không thể tái tạo, ghi chưa kết luận thay vì đoán.
- Dissent là quyền và trách nhiệm của mọi thành viên. Ghi lý do kỹ thuật, không công kích cá nhân.
- Chỉ đánh dấu done sau khi có verify pass không phải từ owner.

## 5. Quản lý bất đồng

- Sau hai lượt trao đổi mà chưa thống nhất, chuyển sang PoC, thử nghiệm hoặc dữ liệu thực tế.
- Nếu không thể kiểm tra thực nghiệm, Lead điều phối reviewer hoặc bỏ phiếu.
- Lỗi nghiêm trọng về mất dữ liệu, quyền truy cập hoặc rò credential phải được nêu ngay và chặn merge cho đến khi giải quyết.

## 6. Giao tiếp và bàn giao

- Nhắm một người thì tag tên; nhắc mã task khi báo việc.
- Tin dài hơn giới hạn nên lưu thành .md trong thư mục phiên/task và gửi đường dẫn.
- Khi rời máy hoặc context sắp reset, gửi handoff gồm task, trạng thái, file, lệnh đã chạy, quyết định và việc kế tiếp.
- Tin bàn giao không có nghĩa là được dừng poll.

## 7. Quyền điều phối và quyền dừng

- Lead phân công territory, làm rõ contract, xử lý xung đột và đề xuất reviewer.
- Thành viên vẫn có quyền dissent độc lập; Lead không được ép xác nhận kết quả chưa kiểm chứng.
- Lead không được chấm dứt vòng poll của thành viên bằng scope freeze, consensus hay standby.
- Theo chỉ thị Admin, mọi agent tiếp tục poll bằng tool call cho đến khi Admin trực tiếp yêu cầu cả đội nghỉ.
