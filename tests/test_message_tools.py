#!/usr/bin/env python3
"""Test cho T10_MARKDOWN_MESSAGING: check_msg.py (preflight) + say.py (gửi có kiểm).

Chạy được bằng 2 cách (stdlib-only, không cần cài thêm):
    python tests/test_message_tools.py
    pytest tests/test_message_tools.py

Không chạm mạng: say.py chỉ test tới ngưỡng preflight FAIL / --check-only PASS,
trường hợp "gửi thật" mock ``send.main``.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_msg  # noqa: E402
import say  # noqa: E402


class FakeSend:
    """Thay cho scripts/send.py khi test: ghi lại argv, LUÔN trả về 0, không chạm mạng."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def main(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        return 0


def write_tmp(text: str, encoding: str = "utf-8") -> Path:
    f = tempfile.NamedTemporaryFile("wb", suffix=".md", delete=False)
    f.write(text.encode(encoding) if isinstance(text, str) else text)
    f.close()
    return Path(f.name)


class ValidateTest(unittest.TestCase):
    def test_tin_sach_dat(self):
        errors, warnings = check_msg.validate("## Tiêu đề\n\nNội dung tiếng Việt có dấu.\n")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_cjk_bi_chan(self):
        errors, _ = check_msg.validate("xin chào 故障 bạn")
        self.assertTrue(any("CJK" in e for e in errors))

    def test_cjk_allow_cjk_ghi_de_chu_dich(self):
        errors, warnings = check_msg.validate("xin chào 故障 bạn", allow_cjk=True)
        self.assertFalse(any("CJK" in e for e in errors))
        self.assertTrue(any("CJK" in w for w in warnings))

    def test_kana_cung_bi_chan(self):
        errors, _ = check_msg.validate("bình thường こんにちは")
        self.assertTrue(any("CJK" in e for e in errors))

    def test_viet_khong_duoc_canh_bao_khong_chan(self):
        # Đủ 5+ từ ASCII-TiếngViệt, 0 dấu → warning nhưng KHÔNG error.
        errors, warnings = check_msg.validate(
            "xin chao cac ban, tin nay khong duoc dau vi viet sai khi gui qua shell"
        )
        self.assertEqual(errors, [])
        self.assertTrue(any("KHÔNG DẤU" in w for w in warnings))

    def test_viet_co_duoc_khong_canh_bao(self):
        _, warnings = check_msg.validate("Xin chào cả nhóm, tin này có dấu đầy đủ.")
        self.assertFalse(any("KHÔNG DẤU" in w for w in warnings))

    def test_qua_4000_ky_tu(self):
        errors, _ = check_msg.validate("a" * 4001)
        self.assertTrue(any("4000" in e for e in errors))

    def test_dung_4000_duoc(self):
        errors, _ = check_msg.validate("a" * 4000)
        self.assertEqual(errors, [])

    def test_fence_le_loi(self):
        errors, _ = check_msg.validate("## Sửa\n```bash\necho chua dong")
        self.assertTrue(any("fence" in e for e in errors))

    def test_fence_chan_ok(self):
        errors, _ = check_msg.validate("```bash\necho dong du\necho ok\n```")
        self.assertEqual(errors, [])

    def test_ky_tu_dieu_khien_loi(self):
        errors, _ = check_msg.validate("tin\x07ký tự điều khiển")
        self.assertTrue(any("điều khiển" in e for e in errors))

    def test_tin_rong_loi(self):
        errors, _ = check_msg.validate("   \n  ")
        self.assertTrue(any("rỗng" in e for e in errors))


class ReadStrictTest(unittest.TestCase):
    def test_doc_utf8_strict_file_hong(self):
        f = write_tmp(b"hop le \xff\xfe hex ky tu loi")
        with self.assertRaises(UnicodeDecodeError):
            check_msg.read_text_strict(str(f))

    def test_doc_utf8_hop_le(self):
        f = write_tmp("tiếng Việt có dấu")
        self.assertEqual(check_msg.read_text_strict(str(f)), "tiếng Việt có dấu")


class RoomHeaderPrivacyTest(unittest.TestCase):
    def _creds(self) -> Path:
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"room": "714-df3f-4e38", "agent_token": "at_SECRET_TOKEN_XYZ", "agent_name": "tester"}, f)
        f.close()
        return Path(f.name)

    def test_room_header_co_room(self):
        header = check_msg.room_header(str(self._creds()))
        self.assertEqual(header, "room=714-df3f-4e38")
        self.assertNotIn("at_SECRET", header)

    def test_cli_in_room_khong_in_token(self):
        f = write_tmp("tin sạch có dấu đầy đủ")
        creds = self._creds()
        out = io.StringIO()
        with redirect_stdout(out):
            rc = check_msg.main([str(f), "--token-file", str(creds)])
        text = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("room=714-df3f-4e38", text)
        self.assertNotIn("at_SECRET_TOKEN_XYZ", text)

    def test_check_msg_fail_exit_1_khi_cjk(self):
        f = write_tmp("có ký tự 故障 lạ")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = check_msg.main([str(f)])
        self.assertEqual(rc, 1)

    def test_check_msg_file_utf8_hong_exit_3(self):
        f = write_tmp(b"\xff\xfe\x00khong phai utf8")
        err = io.StringIO()
        with redirect_stderr(err):
            rc = check_msg.main([str(f)])
        self.assertEqual(rc, 3)


class SayTest(unittest.TestCase):
    def _creds(self) -> Path:
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"room": "714-df3f-4e38", "agent_token": "at_SECRET_TOKEN_XYZ", "agent_name": "tester"}, f)
        f.close()
        return Path(f.name)

    def test_preflight_chan_cjk_truoc_khi_gui(self):
        # CJK không được gửi: preflight FAIL, send.main KHÔNG được gọi (mock để chắc chắn).
        f = write_tmp("tin có 故障 ký tự lạ")
        fake = FakeSend()
        orig = say.send
        say.send = fake
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = say.main(["--file", str(f), "--token-file", str(self._creds())])
        finally:
            say.send = orig
        self.assertEqual(rc, 1)
        self.assertEqual(fake.calls, [], "preflight FAIL thì tuyệt đối không được gửi")
        self.assertIn("CHƯA GỬI", out.getvalue())

    def test_check_only_duoc_khong_gui(self):
        f = write_tmp("## Việc cần làm\n\n- việc một\n- việc hai có dấu\n")
        fake = FakeSend()
        orig = say.send
        say.send = fake
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = say.main(["--file", str(f), "--token-file", str(self._creds()), "--check-only"])
        finally:
            say.send = orig
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, [], "--check-only thì không gửi")
        out_text = out.getvalue()
        self.assertIn("room=714-df3f-4e38", out_text)
        self.assertNotIn("at_SECRET_TOKEN_XYZ", out_text)

    def test_allow_cjk_xa_du_preflight(self):
        f = write_tmp("gửi chủ đích 故障")
        fake = FakeSend()
        orig = say.send
        say.send = fake
        try:
            with redirect_stdout(io.StringIO()):
                rc = say.main(["--file", str(f), "--token-file", str(self._creds()), "--allow-cjk", "--check-only"])
        finally:
            say.send = orig
        self.assertEqual(rc, 0)

    def test_gui_that_pass_go_gui_token(self):
        f = write_tmp("tin sạch gửi thật qua mock\n")
        fake = FakeSend()
        orig = say.send
        say.send = fake
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = say.main(["--file", str(f), "--token-file", str(self._creds())])
        finally:
            say.send = orig
        self.assertEqual(rc, 0)
        self.assertIn("ĐÃ GỬI", out.getvalue())
        self.assertNotIn("at_SECRET_TOKEN_XYZ", out.getvalue())
        self.assertEqual(len(fake.calls), 1)
        # argv nội bộ không lộ token (chỉ --token-file path + --message thân tin).
        argv = fake.calls[0]
        self.assertNotIn("at_SECRET_TOKEN_XYZ", " ".join(argv))
        self.assertIn("--message", argv)

    def test_thieu_file_va_mark_exit_3(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = say.main(["--token-file", str(self._creds())])
        self.assertEqual(rc, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
