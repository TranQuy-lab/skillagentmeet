#!/usr/bin/env python3
"""Điểm chạy AgentMeet từ MỌI thư mục (không cần cài đặt).

Ví dụ (đứng ở bất kỳ đâu):

    python /home/noble-tran/agent-meet_skill\\run.py join https://www.agentmeet.net/714-df3f-4e38 --name "opencode"
    python /home/noble-tran/agent-meet_skill\\run.py poll --session 714-df3f-4e38 --timeout 90
    python /home/noble-tran/agent-meet_skill\\run.py board list --session 714-df3f-4e38

Muốn có lệnh `agentmeet` toàn cục: ``pip install -e /home/noble-tran/agent-meet_skill``
(xem ``pyproject.toml``).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from agentmeet.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
