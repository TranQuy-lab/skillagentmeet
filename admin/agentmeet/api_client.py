"""HTTP Client for AgentMeet API v1 with enhanced stability and error resilience."""

import requests
from typing import Optional, Dict, Any, List, Tuple
from agentmeet.config import build_endpoints, DEFAULT_SERVER_URL, DEFAULT_ROOM_ID
from agentmeet.models import RoomStatus, AgentInfo, ChatMessage


class AgentMeetApiError(Exception):
    """Lỗi phát sinh khi tương tác với API AgentMeet."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class AgentMeetClient:
    """Client giao tiếp với AgentMeet Room API với cơ chế xử lý lỗi an toàn."""

    def __init__(self, room_id: str = DEFAULT_ROOM_ID, server_url: str = DEFAULT_SERVER_URL, timeout: int = 12):
        self.room_id = room_id.strip()
        self.server_url = server_url.strip()
        self.timeout = timeout
        self.endpoints = build_endpoints(self.server_url, self.room_id)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AgentMeet-AdminConsole-PyQt5/2.1",
            "Accept": "application/json",
        })

    def update_config(self, room_id: str, server_url: Optional[str] = None):
        """Cập nhật Room ID hoặc Server URL mới."""
        self.room_id = room_id.strip()
        if server_url:
            self.server_url = server_url.strip()
        self.endpoints = build_endpoints(self.server_url, self.room_id)

    # -------------------------------------------------------------
    # Room Status & Discovery (Không cần Token)
    # -------------------------------------------------------------

    def fetch_status(self) -> RoomStatus:
        """Lấy thông tin trạng thái phòng từ endpoint /status."""
        url = self.endpoints["status"]
        try:
            resp = self.session.get(url, timeout=min(self.timeout, 8))
            resp.raise_for_status()
            data = resp.json()
            return RoomStatus.from_dict(data)
        except requests.exceptions.Timeout:
            raise AgentMeetApiError("Hết thời gian chờ (Timeout) khi tải trạng thái phòng.")
        except requests.exceptions.ConnectionError:
            raise AgentMeetApiError("Không thể kết nối đến máy chủ AgentMeet. Vui lòng kiểm tra mạng.")
        except requests.RequestException as e:
            text = getattr(e.response, "text", "")
            code = getattr(e.response, "status_code", None)
            raise AgentMeetApiError(f"Không thể lấy trạng thái phòng: {e}", status_code=code, response_text=text)

    def fetch_transcript(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Lấy danh sách tin nhắn và agents từ endpoint /transcript."""
        url = self.endpoints["transcript"]
        params = {"limit": limit, "offset": offset}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            raise AgentMeetApiError("Hết thời gian chờ (Timeout) khi tải transcript.")
        except requests.exceptions.ConnectionError:
            raise AgentMeetApiError("Lỗi kết nối mạng khi tải transcript.")
        except requests.RequestException as e:
            text = getattr(e.response, "text", "")
            code = getattr(e.response, "status_code", None)
            raise AgentMeetApiError(f"Không thể tải transcript: {e}", status_code=code, response_text=text)

    def fetch_all_messages(self, limit: int = 100) -> List[ChatMessage]:
        data = self.fetch_transcript(limit=limit)
        raw_msgs = data.get("messages", [])
        return [ChatMessage.from_dict(m) for m in raw_msgs]

    def fetch_agents(self) -> List[AgentInfo]:
        """Lấy danh sách các agent đang có mặt trong phòng từ transcript."""
        data = self.fetch_transcript(limit=1)
        raw_agents = data.get("agents", [])
        return [AgentInfo.from_dict(a) for a in raw_agents if isinstance(a, dict)]

    # -------------------------------------------------------------
    # Agent Session Actions (Yêu cầu hoặc tạo Agent Token)
    # -------------------------------------------------------------

    def join_room(self, agent_name: str = "Admin") -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Tham gia phòng họp.
        Trả về: (agent_id, agent_token, initial_transcript)
        """
        url = self.endpoints["join"]
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            agent_id = data.get("agent_id")
            agent_token = data.get("agent_token")
            transcript = data.get("transcript", [])

            if not agent_token:
                raise AgentMeetApiError(f"Server không trả về agent_token: {data}")

            return agent_id, agent_token, transcript
        except requests.exceptions.Timeout:
            raise AgentMeetApiError("Kết nối vào phòng quá hạn thời gian (Timeout).")
        except requests.exceptions.ConnectionError:
            raise AgentMeetApiError("Không thể kết nối đến máy chủ AgentMeet.")
        except requests.RequestException as e:
            text = getattr(e.response, "text", "")
            code = getattr(e.response, "status_code", None)
            raise AgentMeetApiError(f"Lỗi tham gia phòng họp: {e}", status_code=code, response_text=text)

    def send_message(self, agent_token: str, agent_name: str, content: str) -> Dict[str, Any]:
        """Gửi một tin nhắn mới vào phòng."""
        url = self.endpoints["message"]
        payload = {
            "agent_token": agent_token,
            "agent_name": agent_name.strip() or "Admin",
            "content": content,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            raise AgentMeetApiError("Gửi tin nhắn quá thời gian chờ (Timeout).")
        except requests.exceptions.ConnectionError:
            raise AgentMeetApiError("Mất kết nối mạng khi gửi tin nhắn.")
        except requests.RequestException as e:
            text = getattr(e.response, "text", "")
            code = getattr(e.response, "status_code", None)
            raise AgentMeetApiError(f"Lỗi gửi tin nhắn: {e}", status_code=code, response_text=text)

    def read_new_messages(self, agent_token: str) -> List[Dict[str, Any]]:
        """Đọc các tin nhắn mới gửi đến kể từ lần đọc trước (dựa trên token)."""
        url = self.endpoints["read"]
        params = {"token": agent_token}
        try:
            resp = self.session.get(url, params=params, timeout=min(self.timeout, 7))
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return (
                    data.get("messages")
                    or data.get("replies")
                    or data.get("transcript")
                    or []
                )
            return []
        except requests.exceptions.Timeout:
            # Polling timeout is normal in slow networks, return empty list
            return []
        except requests.exceptions.ConnectionError:
            raise AgentMeetApiError("Mất kết nối với máy chủ khi đọc tin nhắn.")
        except requests.RequestException as e:
            text = getattr(e.response, "text", "")
            code = getattr(e.response, "status_code", None)
            raise AgentMeetApiError(f"Lỗi kiểm tra tin nhắn mới: {e}", status_code=code, response_text=text)

    def leave_room(self, agent_token: str) -> bool:
        """Rời phòng họp và giải phóng session."""
        url = self.endpoints["leave"]
        payload = {"agent_token": agent_token}
        try:
            resp = self.session.post(url, json=payload, timeout=4)
            resp.raise_for_status()
            return True
        except Exception:
            return False
