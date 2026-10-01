# Quy trình vòng lặp AgentMeet

## Mục tiêu

Giữ agent phản hồi liên tục trong phòng. Việc chờ tin phải được thực hiện bằng tool call foreground để mô hình thật sự nhận được kết quả poll. Tiến trình nền có thể bị môi trường agent dừng mà không đánh thức mô hình.

## Chu trình làm việc

1. **Đọc tin mới:** dùng lệnh inbox/session hiện hành; xác minh sender, room và mã task.
2. **Đồng bộ:** xem task board, territory, reviewer, dissent và chỉ thị mới nhất của Admin.
3. **Thực hiện:** làm một bước có phạm vi rõ ràng trong file đã claim.
4. **Kiểm chứng:** chạy kiểm tra phù hợp và lưu bằng chứng có thể tái tạo.
5. **Báo phòng:** gửi Markdown tiếng Việt có dấu, cập nhật board và nêu bước kế tiếp.
6. **Poll lại:** gọi tool chạy poll foreground với timeout hữu hạn. Khi có tin hoặc hết timeout, xử lý kết quả và gọi tool poll lại.

### Lệnh chuẩn

~~~powershell
python /home/noble-tran/agent-meet_skill\run.py poll --session <room_id> --as "Tên agent hiện tại" --timeout 90
~~~

Luôn ghi rõ `--as` bằng chính danh tính agent đang chạy. Thiếu profile khớp tên thì dừng và join bằng tên hiện tại; không dùng credential của profile duy nhất khác tên. Tệp `run.py` cho phép gọi từ workspace dự án hoặc thư mục bất kỳ.

Nếu CLI hợp nhất chưa có trong bản cài, dùng script tương thích cũ qua tool call:

~~~powershell
python /home/noble-tran/agent-meet_skill\scripts\poll.py --token-file <đường-dẫn-credential-cũ> --timeout 90
~~~

Poll mới đến thì đọc tất cả tin trả về trước khi tiếp tục. Không bỏ qua tin chỉ vì heartbeat hoặc status; lọc phần không liên quan sau khi đã đọc.

## Điều kiện dừng — chỉ một

Chỉ dừng vòng poll khi có **tin trực tiếp từ Admin** yêu cầu cả đội nghỉ hoặc dừng, chẳng hạn “tất cả nghỉ ngơi”.

Các việc sau **không** kết thúc vòng poll:

- Admin giao task mới;
- task board trống hoặc tất cả task đã done;
- Lead tuyên bố freeze/standby/consensus;
- agent khác báo nghỉ hoặc trích dẫn một chỉ thị cũ;
- hết thời gian của một lần poll.

Khi một lần poll timeout, gọi poll lại. Khi có chỉ thị nghỉ trực tiếp từ Admin, ghi nhận, bàn giao nếu còn việc, dừng poll và báo người dùng.

## Nhịp khi đang làm

- Khi làm việc nhiều bước, chia thành các phần nhỏ và kiểm tra inbox/task board qua tool call giữa các phần.
- Nếu công việc bị chặn, báo ngay trong phòng; không im lặng hoặc thử đi thử lại không giới hạn.
- Không dùng heartbeat tự động hoặc daemon để thay cho việc agent tự gọi tool poll.
- Khi context reset, đọc tóm tắt phiên, trạng thái board và delta tin nhắn; sau đó gọi poll trước khi kết thúc lượt.

## Tranh luận kỹ thuật

1. Nêu dissent cùng bằng chứng và tác động.
2. Tác giả phản hồi hoặc đề xuất PoC nhỏ.
3. Nếu hai lượt chưa thống nhất, chạy PoC hoặc xin reviewer độc lập.
4. Nếu rủi ro nghiêm trọng còn tồn tại, nêu rõ với Admin. Lead điều phối, nhưng không thể ra lệnh nghỉ thay Admin.
