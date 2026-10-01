"""Data models for AgentMeet console."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ChatMessage:
    agent_name: str
    content: str
    message_id: Optional[int] = None
    agent_id: Optional[str] = None
    timestamp: str = ""
    read_by: List[str] = field(default_factory=list)
    is_self: bool = False
    is_system: bool = False
    is_error: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any], current_agent_name: str = "", current_agent_id: str = "") -> "ChatMessage":
        if isinstance(data, str):
            return cls(agent_name="System", content=data, is_system=True)

        msg_id = data.get("message_id")
        agent_id = data.get("agent_id")
        name = (
            data.get("agent_name")
            or data.get("name")
            or data.get("sender")
            or ("System" if not agent_id else "Unknown Agent")
        )
        content = (
            data.get("content")
            or data.get("message")
            or data.get("text")
            or ""
        )
        raw_ts = data.get("timestamp") or data.get("created_at") or ""
        read_by = data.get("read_by") or []

        # Check self
        is_self = False
        if current_agent_id and agent_id and current_agent_id == agent_id:
            is_self = True
        elif current_agent_name and name.strip().lower() == current_agent_name.strip().lower():
            is_self = True

        return cls(
            message_id=msg_id,
            agent_id=agent_id,
            agent_name=name,
            content=str(content),
            timestamp=str(raw_ts),
            read_by=list(read_by),
            is_self=is_self,
            is_system=(name.lower() in ("system", "[system]")),
        )

    def display_time(self) -> str:
        """Chuyển đổi timestamp ISO sang giờ:phút:giây dễ đọc."""
        if not self.timestamp:
            return ""
        try:
            # Handle ISO string like "2026-09-23T09:05:38.888596+00:00"
            clean_ts = self.timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            # Localized time
            return dt.strftime("%H:%M:%S")
        except Exception:
            # Fallback
            if "T" in self.timestamp:
                parts = self.timestamp.split("T")
                if len(parts) > 1:
                    return parts[1].split(".")[0]
            return self.timestamp


@dataclass
class AgentInfo:
    agent_id: str
    agent_name: str
    status: str = "active"  # "active", "left", "pending"
    created_at: str = ""
    activated_at: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        return cls(
            agent_id=data.get("agent_id", ""),
            agent_name=data.get("agent_name", "Unknown"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", ""),
            activated_at=data.get("activated_at", ""),
        )

    @property
    def is_active(self) -> bool:
        return self.status.lower() == "active"


@dataclass
class RoomStatus:
    room_code: str
    state: str = "unknown"
    active_agents: int = 0
    pending_agents: int = 0
    message_count: int = 0
    max_messages: int = 500
    created_at: str = ""
    first_message_at: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoomStatus":
        agents_data = data.get("agents", {})
        if isinstance(agents_data, dict):
            active = agents_data.get("active", 0)
            pending = agents_data.get("pending", 0)
        elif isinstance(agents_data, list):
            active = sum(1 for a in agents_data if isinstance(a, dict) and a.get("status") == "active")
            pending = sum(1 for a in agents_data if isinstance(a, dict) and a.get("status") == "pending")
        else:
            active = 0
            pending = 0

        return cls(
            room_code=data.get("room_code", ""),
            state=data.get("state", "active"),
            active_agents=active,
            pending_agents=pending,
            message_count=data.get("message_count", 0),
            max_messages=data.get("max_messages", 500),
            created_at=data.get("created_at", ""),
            first_message_at=data.get("first_message_at", ""),
        )
