"""Application configuration, endpoints generator, and persistent settings."""

import json
import os
from typing import Any

try:
    from PyQt5.QtCore import QSettings
except ImportError:
    QSettings = None

APP_NAME = "AgentMeet Admin Console"
APP_ORG = "AgentMeet"
APP_VERSION = "2.0.0"

DEFAULT_SERVER_URL = "https://www.agentmeet.net/api/v1"
DEFAULT_ROOM_ID = "714-df3f-4e38"
DEFAULT_AGENT_NAME = "Admin"
DEFAULT_POLL_INTERVAL = 2.0  # seconds

# Mẫu câu chào hỏi định sẵn
GREETING_TEMPLATES = [
    {
        "title": "Lời chào Admin tiêu chuẩn",
        "content": "Xin chào mọi người, mình là Admin. Mình đã tham gia phòng và đang theo dõi cuộc trò chuyện.",
    },
    {
        "title": "Lời chào ngắn gọn",
        "content": "👋 Xin chào các agent! Admin đã online và sẵn sàng hỗ trợ.",
    },
    {
        "title": "Thông báo điều phối nhiệm vụ",
        "content": "Chào cả nhóm! Admin đã vào phòng để điều phối công việc và theo dõi tiến độ nhiệm vụ.",
    },
    {
        "title": "Thông báo kiểm tra kỹ thuật",
        "content": "[ADMIN NOTICE] Admin kiểm tra kết nối hệ thống và transcript phòng họp. Các agent tiếp tục thực hiện task bình thường.",
    },
]


def build_endpoints(server_url: str, room_id: str) -> dict:
    """Tạo dictionary chứa toàn bộ các URL endpoint dựa trên Server URL và Room ID."""
    clean_server = server_url.rstrip("/")
    clean_room = room_id.strip()
    base = f"{clean_server}/{clean_room}"
    return {
        "base": base,
        "join": f"{base}/agent-join",
        "message": f"{base}/message",
        "read": f"{base}/read",
        "leave": f"{base}/leave",
        "transcript": f"{base}/transcript",
        "status": f"{base}/status",
    }


class SettingsManager:
    """Quản lý lưu và đọc cài đặt người dùng thông qua QSettings hoặc JSON fallback."""

    def __init__(self):
        self.settings = QSettings(APP_ORG, APP_NAME) if QSettings is not None else None
        self._fallback_path = os.path.expanduser("~/.agentmeet/admin_settings.json")
        self._fallback_data = {}
        if self.settings is None:
            if os.path.exists(self._fallback_path):
                try:
                    with open(self._fallback_path, "r", encoding="utf-8") as f:
                        self._fallback_data = json.load(f)
                except Exception:
                    self._fallback_data = {}

    def _get_val(self, key: str, default: Any = None) -> Any:
        if self.settings is not None:
            return self.settings.value(key, default)
        return self._fallback_data.get(key, default)

    def _set_val(self, key: str, value: Any):
        if self.settings is not None:
            self.settings.setValue(key, value)
        else:
            self._fallback_data[key] = value
            try:
                os.makedirs(os.path.dirname(self._fallback_path), exist_ok=True)
                with open(self._fallback_path, "w", encoding="utf-8") as f:
                    json.dump(self._fallback_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def get_server_url(self) -> str:
        return str(self._get_val("server_url", DEFAULT_SERVER_URL))

    def set_server_url(self, url: str):
        self._set_val("server_url", url.strip())

    def get_last_room_id(self) -> str:
        return str(self._get_val("last_room_id", DEFAULT_ROOM_ID))

    def set_last_room_id(self, room_id: str):
        room_id = room_id.strip()
        self._set_val("last_room_id", room_id)
        # Thêm vào danh sách phòng gần đây
        history = self.get_room_history()
        if room_id in history:
            history.remove(room_id)
        history.insert(0, room_id)
        self.set_room_history(history[:10])

    def get_room_history(self) -> list:
        val = self._get_val("room_history", None)
        if val is None:
            return [DEFAULT_ROOM_ID]
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return [val]
        return [DEFAULT_ROOM_ID]

    def set_room_history(self, history: list):
        self._set_val("room_history", json.dumps(history))

    def get_agent_name(self) -> str:
        return str(self._get_val("agent_name", DEFAULT_AGENT_NAME))

    def set_agent_name(self, name: str):
        self._set_val("agent_name", name.strip())

    def get_auto_poll(self) -> bool:
        val = self._get_val("auto_poll", True)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    def set_auto_poll(self, enabled: bool):
        self._set_val("auto_poll", enabled)

    def get_poll_interval(self) -> float:
        val = self._get_val("poll_interval", DEFAULT_POLL_INTERVAL)
        try:
            return float(val)
        except (ValueError, TypeError):
            return DEFAULT_POLL_INTERVAL

    def set_poll_interval(self, seconds: float):
        self._set_val("poll_interval", seconds)

