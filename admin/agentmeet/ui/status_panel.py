"""Panel displaying room metadata and live capacity status with Light theme and large typography."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton
)
from PyQt5.QtCore import pyqtSignal
from agentmeet.models import RoomStatus


class RoomStatusPanel(QWidget):
    """Bảng hiển thị trạng thái phòng, dung lượng tin nhắn, và số lượng agent."""

    sig_fetch_status_requested = pyqtSignal()

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.last_status = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        self.lbl_title = QLabel("📊 <b>Trạng thái phòng</b>")
        self.lbl_title.setStyleSheet("font-size: 14px;")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()

        self.btn_fetch = QPushButton("🔄 Fetch")
        self.btn_fetch.setToolTip("Lấy thông tin trạng thái phòng từ API /status")
        self.btn_fetch.clicked.connect(self.sig_fetch_status_requested.emit)
        hdr.addWidget(self.btn_fetch)
        layout.addLayout(hdr)

        # Details Box with larger font
        self.lbl_room_code = QLabel("Mã phòng: <b>—</b>")
        self.lbl_room_state = QLabel("Trạng thái: <b>—</b>")
        self.lbl_agents_count = QLabel("Số Agent: <b>—</b>")
        self.lbl_msg_count = QLabel("Tin nhắn: <b>0 / 500</b>")

        for lbl in (self.lbl_room_code, self.lbl_room_state, self.lbl_agents_count, self.lbl_msg_count):
            lbl.setStyleSheet("font-size: 14px; margin-bottom: 2px;")
            layout.addWidget(lbl)

        # Capacity Progress Bar
        self.prog_messages = QProgressBar()
        self.prog_messages.setRange(0, 500)
        self.prog_messages.setValue(0)
        self.prog_messages.setMinimumHeight(24)
        self.prog_messages.setFormat("%v / %m (%p%)")
        layout.addWidget(self.prog_messages)

        # Time details
        self.lbl_created_at = QLabel("Khởi tạo: —")
        self.lbl_created_at.setStyleSheet("color: #64748b; font-size: 12px;")
        self.lbl_created_at.setWordWrap(True)
        layout.addWidget(self.lbl_created_at)

        layout.addStretch()

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        if self.last_status:
            self.update_status(self.last_status)

    def update_status(self, status: RoomStatus):
        self.last_status = status
        code_color = "#0284c7" if not self.dark_mode else "#38bdf8"
        self.lbl_room_code.setText(f"Mã phòng: <b style='color:{code_color};'>{status.room_code}</b>")

        if status.state == "active":
            state_color = "#16a34a" if not self.dark_mode else "#4ade80"
        else:
            state_color = "#dc2626" if not self.dark_mode else "#f87171"
        self.lbl_room_state.setText(f"Trạng thái: <b style='color:{state_color};'>{status.state.upper()}</b>")

        agent_color = "#16a34a" if not self.dark_mode else "#4ade80"
        self.lbl_agents_count.setText(
            f"Số Agent: <b style='color:{agent_color};'>{status.active_agents} online</b> "
            f"({status.pending_agents} chờ)"
        )

        max_msg = status.max_messages or 500
        cnt = status.message_count or 0
        self.lbl_msg_count.setText(f"Tin nhắn: <b>{cnt} / {max_msg}</b>")

        self.prog_messages.setMaximum(max_msg)
        self.prog_messages.setValue(cnt)

        # Color progression
        pct = (cnt / max_msg) * 100 if max_msg else 0
        if pct >= 90:
            chunk_color = "#dc2626"
        elif pct >= 70:
            chunk_color = "#d97706"
        else:
            chunk_color = "#2563eb"

        self.prog_messages.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {chunk_color}; border-radius: 4px; }}"
        )

        if status.created_at:
            c_time = status.created_at.replace("T", " ").split(".")[0]
            self.lbl_created_at.setText(f"Tạo lúc: {c_time}")
