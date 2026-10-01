# Quyền điều phối và phản biện độc lập

Tài liệu này quy định cách nhóm xác định Lead, phân chia việc và xử lý phản biện. Luôn áp dụng chỉ thị trực tiếp mới nhất của Admin.

## 1. Ưu tiên chỉ định của Admin

- Nếu Admin chỉ định một agent làm Lead, chỉ định đó có hiệu lực ngay và ưu tiên hơn kết quả bầu cử cũ hoặc trạng thái election đã lưu.
- Lead được Admin chỉ định là điều phối viên: phân chia territory, cập nhật task board, ghép reviewer và tổng hợp tiến độ.
- Không cần buộc Admin lặp lại chỉ định qua một cuộc bầu cử. Nếu trạng thái bầu cử trên máy chủ còn tên Lead cũ, ghi rõ Admin đã chỉ định Lead mới; không tự tạo phiếu bầu thay cho thành viên.
- Chỉ khi Admin chưa chỉ định Lead và nhóm có ít nhất ba agent đang hoạt động thì dùng bầu cử trong mục 2.
- Lead không được kết thúc vòng poll thay Admin. Chỉ lệnh nghỉ trực tiếp từ Admin mới dừng poll của nhóm; xem [LOOP_PROTOCOL.md](./LOOP_PROTOCOL.md).

## 2. Bầu cử khi Admin chưa chỉ định Lead

1. Một thành viên đề cử ứng viên qua lệnh nominate và nêu lý do.
2. Mỗi agent đang hoạt động có một phiếu; gửi vote qua lệnh tương ứng.
3. Kiểm phiếu theo quy tắc đa số quá bán do election CLI hiển thị.
4. Người điều phối gửi declare khi đã đạt ngưỡng.
5. Kiểm tra đúng mã phòng trên đầu ra trước khi tin kết quả. Nếu có chỉ định Admin mới, mục 1 được áp dụng ngay.

Khi cần bầu cử, dùng các lệnh nominate, vote, tally và declare của election CLI theo hướng dẫn trong [CHEATSHEET.md](./CHEATSHEET.md). Không tự bầu lại nếu Admin đã chỉ định Lead.

## 3. Trách nhiệm của Lead

- Tạo task có mục tiêu, file territory, tiêu chí chấp nhận, owner và reviewer.
- Đảm bảo mỗi file chỉ có một owner tại một thời điểm; chốt contract trước khi giao các phần liên quan.
- Yêu cầu cập nhật trạng thái và bằng chứng; không gọi việc là done trước khi có verify độc lập.
- Điều phối xung đột, nhưng không ép thành viên rút dissent hoặc xác nhận điều chưa kiểm chứng.
- Thông báo quyết định bằng Markdown tiếng Việt có dấu và nhắc mã task.

## 4. Dissent và veto kỹ thuật

Mọi thành viên đều có quyền nêu phản biện. Dissent cần ghi:
- mã task và file/vị trí liên quan;
- bằng chứng có thể tái tạo;
- mức độ ảnh hưởng và thay đổi cần thiết.

Lỗi nghiêm trọng như mất dữ liệu, rò credential, bypass xác thực hoặc phá tương thích phải chặn việc chốt/merge cho đến khi được xử lý. Sau tối đa hai lượt tranh luận, chuyển sang PoC hoặc reviewer độc lập; nếu vẫn không giải quyết được, nhờ Admin phân xử.

Gỡ dissent phải ghi sự kiện giải quyết để giữ lại lịch sử; không xóa dấu vết phản biện cũ. Xem định dạng envelope trong [PROTOCOL.md](./PROTOCOL.md) và quy trình nhóm trong [TEAMWORK.md](./TEAMWORK.md).

## 5. Mẫu xác nhận vai trò

Khi Admin chỉ định Lead hoặc một cuộc bầu cử hợp lệ đã hoàn tất, xác nhận bằng Markdown tiếng Việt. Không tạo phiếu hoặc envelope giả để đổi kết quả election:

~~~text
## Xác nhận vai trò điều phối

- Nguồn: chỉ định trực tiếp của Admin hoặc kết quả election trong room.
- Lead: <tên agent>.
- Vai trò: phân chia territory, đồng bộ board và điều phối review.
- Quyền phản biện: mọi thành viên giữ quyền dissent độc lập.
- Poll: tiếp tục đến khi Admin trực tiếp yêu cầu cả đội nghỉ.
~~~
