#!/usr/bin/env python3
"""Gửi tin Markdown UTF-8 đến phòng AgentMeet — 1 lệnh, không cần viết script mới.

Luôn chạy preflight ``check_msg.py`` TRƯỚC (CJK không dấu, 4000 ký tự, fence, điều khiển),
in ``room=<ma_phong>`` ở đầu kết quả và KHÔNG BAO GIỜ in token (credential giữ kín).

Nguồn tin: ``--file tin.md`` (khuyên dùng) hoặc ``-`` đọc stdin. Tránh truyền Unicode
qua tham số shell — đây chỉ là fallback nội bộ quy trình (argv in-process).

Exit codes: ``0`` đã gửi, ``1`` preflight FAIL (chưa gửi gì), ``3`` thiếu credential/tham số, ``4`` lỗi API.

Ví dụ::

    python scripts/say.py --file tin.md --token-file creds_714.json
    python scripts/say.py --file tin.md --allow-cjk        # ghi đè chủ đích ký tự CJK
    python scripts/say.py --file qua-dai.md --split        # cho phép chia tin > 4000 ký tự
    cat tin.md | python scripts/say.py - --token-file creds_714.json
    python scripts/say.py --file tin.md --check-only       # chỉ kiểm, không gửi
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR.parent))

from agentmeet import DEFAULT_CREDS_PATH, load_credentials  # noqa: E402
from check_msg import MSG_LIMIT_DEFAULT, read_text_strict, room_header, validate  # noqa: E402

import send  # noqa: E402  (scripts/send.py — đường gửi dùng chung; import ở module level để test mock được say.send)

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_CONFIG = 3
EXIT_API = 4


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gửi tin Markdown UTF-8 có preflight kiểm tra.")
    p.add_argument("stdin_marker", nargs="?", help="'-' để đọc thân tin từ stdin")
    p.add_argument("--file", "-f", help="đọc thân tin từ file .md (UTF-8 strict)")
    p.add_argument("--token-file", default=DEFAULT_CREDS_PATH, help=f"credential JSON (mặc định {DEFAULT_CREDS_PATH})")
    p.add_argument("--allow-cjk", action="store_true", help="CHO PHÉP ký tự CJK/kana/hangul trong tin")
    p.add_argument("--split", action="store_true", help="cho phép chia tự động tin > 4000 ký tự")
    p.add_argument("--check-only", action="store_true", help="chỉ chạy preflight, KHÔNG gửi")
    p.add_argument("--name", help="ghi đè agent_name khi gửi")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # 1) Đọc thân tin UTF-8 strict.
    if args.file:
        source = args.file
    elif args.stdin_marker == "-":
        source = "-"
    else:
        print("error: cần --file tin.md hoặc '-' (stdin)", file=sys.stderr)
        return EXIT_CONFIG
    try:
        body = read_text_strict(source).rstrip("\n")
    except UnicodeDecodeError as exc:
        print(f"[{room_header(args.token_file)}] error: nguồn không phải UTF-8 hợp lệ ({exc})", file=sys.stderr)
        return EXIT_FAIL
    except OSError as exc:
        print(f"error: không đọc được nguồn ({exc})", file=sys.stderr)
        return EXIT_CONFIG

    # 2) Preflight — chặn trước khi gửi.
    max_chars = MSG_LIMIT_DEFAULT  # --split không đổi ngưỡng check; say.py sẽ chia ở tầng gửi
    errors, warnings = validate(body, allow_cjk=args.allow_cjk, max_chars=max_chars)
    if errors and len(body) > MSG_LIMIT_DEFAULT and args.split:
        # Trường hợp duy nhất được bỏ qua nhờ --split: quá ký tự (các lỗi khác vẫn chặn).
        errors = [e for e in errors if not e.startswith("quá ")]

    print(f"[{room_header(args.token_file)}] say: {len(body)} ký tự, {len(warnings)} cảnh báo")
    for w in warnings:
        print(f"  ⚠ warning: {w}")
    if errors:
        for e in errors:
            print(f"  ✗ error: {e}")
        print("KẾT LUẬN: preflight FAIL — CHƯA GỬI gì. Sửa tin hoặc dùng --allow-cjk/--split nếu chủ đích.")
        return EXIT_FAIL

    if args.check_only:
        print("KẾT LUẬN: preflight ĐẠT (--check-only nên không gửi).")
        return EXIT_OK

    # 3) Gửi — tái dùng đường gửi có sẵn của send.py (argv in-process, không qua shell).
    send_argv = ["--token-file", args.token_file]
    if args.name:
        send_argv += ["--name", args.name]
    if args.split:
        send_argv += []  # send.py tự chia >4000 trừ khi --no-split
    else:
        send_argv += ["--no-split"]  # đã qua preflight nên chắc ≤ 4000; nếu server từ chối thì báo lỗi rõ
    send_argv += ["--message", body]
    rc = send.main(send_argv)
    if rc == 0:
        print(f"[{room_header(args.token_file)}] ĐÃ GỬI.")
        return EXIT_OK
    if rc == 3:
        return EXIT_CONFIG
    return EXIT_API


if __name__ == "__main__":
    raise SystemExit(main())
