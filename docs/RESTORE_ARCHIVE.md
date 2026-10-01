# Hướng dẫn đối chiếu và khôi phục kho lưu trữ lịch sử

Tài liệu này ghi nhận nguồn gốc và cách khôi phục lại các tệp nháp, nhật ký và tin nhắn cũ đã được dọn khỏi thư mục gốc của `agent-meet_skill` theo chỉ đạo của Admin (Msg #396, Task `T14_CLEAN_SKILL_REPO`).

## 1. Vị trí kho lưu trữ

Toàn bộ **454 tệp cũ** (gồm 310 tệp `.txt`, 66 tệp `.py` nháp, 58 tệp `.md` nhật ký, các credential và profiling cũ) đã được đóng gói an toàn vào hai vị trí:

1. **Kho lưu trữ người dùng:**
   `~/.agentmeet/archive/legacy_skill_trash_backup.zip`
2. **Kho lưu trữ dự phòng tại skill (được bảo vệ trong `.gitignore`):**
   `/home/noble-tran/agent-meet_skill\legacy_trash_archive.zip` (kích thước ~1.8 MB nén toàn vẹn).

## 2. Cách xem danh sách tệp trong kho lưu trữ

Không cần giải nén, có thể xem danh sách toàn bộ các tệp bằng lệnh:

```bash
python -c "import zipfile, pathlib; zf = zipfile.ZipFile(pathlib.Path.home() / '.agentmeet' / 'archive' / 'legacy_skill_trash_backup.zip'); print(f'Tong so tep: {len(zf.namelist())}'); print('\n'.join(zf.namelist()[:20]))"
```

## 3. Cách khôi phục một tệp cụ thể khi cần đối chiếu

Nếu cần lấy lại một biên bản hay kịch bản cũ (ví dụ `master_audit_report.md`):

```bash
python -c "import zipfile, pathlib; zf = zipfile.ZipFile(pathlib.Path.home() / '.agentmeet' / 'archive' / 'legacy_skill_trash_backup.zip'); zf.extract('master_audit_report.md', 'restore_output')"
```

Tệp sẽ được giải nén vào thư mục `restore_output/` mà không làm bẩn lại thư mục gốc của skill.

## 4. Quy tắc giữ gìn vệ sinh thư mục

1. Mọi credential phiên phải lưu tại `~/.agentmeet/sessions/<mã_phòng>/<tên-agent>/creds.json`.
2. Mọi tệp nháp, tin nhắn gửi tạm phải tạo trong workspace dự án (như `E:\Networking`) hoặc thư mục tạm `scratch/`, tuyệt đối không lưu ở root của skill.
3. Tệp `.gitignore` của skill đã được thiết lập nghiêm ngặt để ngăn ngừa việc đưa tệp rác vào quản lý phiên bản.
