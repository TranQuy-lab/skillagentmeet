"""Panel showing list of agents/participants in the room with status badges and filter actions."""

from typing import List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QMenu
)
from PyQt5.QtCore import pyqtSignal, Qt
from agentmeet.models import AgentInfo


class AgentsPanel(QWidget):
    """Bảng hiển thị danh sách các Agent tham gia phòng."""

    sig_fetch_agents_requested = pyqtSignal()
    sig_filter_agent_selected = pyqtSignal(str)
    sig_mention_agent_requested = pyqtSignal(str)

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.agents: List[AgentInfo] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header with Title and Fetch button
        hdr = QHBoxLayout()
        self.lbl_title = QLabel("👥 <b>Thành viên phòng</b>")
        self.lbl_title.setStyleSheet("font-size: 14px;")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()

        self.btn_refresh = QPushButton("🔄 Fetch")
        self.btn_refresh.setToolTip("Lấy danh sách các agent từ API /transcript")
        self.btn_refresh.clicked.connect(self.sig_fetch_agents_requested.emit)
        hdr.addWidget(self.btn_refresh)
        layout.addLayout(hdr)

        # Status summary label
        self.lbl_summary = QLabel("Hoạt động: 0 | Đã rời: 0")
        self.lbl_summary.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.lbl_summary)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        hint = QLabel("💡 <i>Nhấp đúp hoặc chuột phải vào agent để lọc tin hoặc tag @tên</i>")
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        if self.agents:
            self.set_agents(self.agents)

    def set_agents(self, agents: List[AgentInfo]):
        self.agents = agents
        self.list_widget.clear()

        active_cnt = 0
        left_cnt = 0

        for a in agents:
            if a.status == "active":
                active_cnt += 1
                status_icon = "🟢"
                status_text = "Hoạt động"
            elif a.status == "left":
                left_cnt += 1
                status_icon = "⚪"
                status_text = "Đã rời"
            else:
                status_icon = "🟡"
                status_text = a.status

            item = QListWidgetItem()
            display_text = f"{status_icon} {a.agent_name}\n    ID: {a.agent_id} • [{status_text}]"
            item.setText(display_text)
            item.setData(Qt.UserRole, a.agent_name)
            item.setData(Qt.UserRole + 1, a.agent_id)
            self.list_widget.addItem(item)

        active_color = "#16a34a" if not self.dark_mode else "#4ade80"
        self.lbl_summary.setText(f"Hoạt động: <b style='color:{active_color};'>{active_cnt}</b> | Đã rời: <b style='color:#64748b;'>{left_cnt}</b>")

    def on_item_double_clicked(self, item: QListWidgetItem):
        name = item.data(Qt.UserRole)
        if name:
            self.sig_filter_agent_selected.emit(name)

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        name = item.data(Qt.UserRole)
        agent_id = item.data(Qt.UserRole + 1)

        menu = QMenu(self)
        act_filter = menu.addAction(f"🔍 Chỉ xem tin của '{name}'")
        act_mention = menu.addAction(f"💬 Nhắc đến @{name}")
        act_copy_id = menu.addAction(f"📋 Sao chép Agent ID ({agent_id})")

        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        if action == act_filter:
            self.sig_filter_agent_selected.emit(name)
        elif action == act_mention:
            self.sig_mention_agent_requested.emit(f"@{name} ")
        elif action == act_copy_id:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(agent_id)
