"""Connection bar widget with Room ID input, credentials, connection controls, and Greeting button."""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QApplication, QFrame, QToolButton
)
from PyQt5.QtCore import pyqtSignal, Qt
from agentmeet.config import DEFAULT_ROOM_ID, DEFAULT_AGENT_NAME, DEFAULT_SERVER_URL


class ConnectionBar(QWidget):
    """
    Thanh điều khiển kết nối:
    - Nhập Room ID (hỗ trợ lưu lịch sử các ID gần đây)
    - Nhập Tên đại diện (Agent Name)
    - Nút Kết nối / Rời phòng
    - Nút Gửi lời chào (chỉ kích hoạt sau khi đã kết nối)
    - Thông tin phiên (Agent ID, Token với tính năng sao chép và ẩn/hiện)
    """

    sig_connect_requested = pyqtSignal(str, str, str)  # room_id, agent_name, server_url
    sig_leave_requested = pyqtSignal()
    sig_greeting_requested = pyqtSignal()
    sig_fetch_status_requested = pyqtSignal()

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.agent_id = ""
        self.agent_token = ""
        self.is_connected = False
        self._token_visible = False

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # -----------------------------
        # Row 1: Connection inputs & primary actions
        # -----------------------------
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        # Room ID
        lbl_room = QLabel("<b>Mã phòng (Room ID):</b>")
        self.combo_room_id = QComboBox()
        self.combo_room_id.setEditable(True)
        self.combo_room_id.setMinimumWidth(200)
        self.combo_room_id.addItem(DEFAULT_ROOM_ID)
        self.combo_room_id.lineEdit().setPlaceholderText("Nhập mã phòng (vd: 714-df3f-4e38)")

        row1.addWidget(lbl_room)
        row1.addWidget(self.combo_room_id)

        # Agent Name
        lbl_name = QLabel("<b>Tên hiển thị:</b>")
        self.edit_agent_name = QLineEdit(DEFAULT_AGENT_NAME)
        self.edit_agent_name.setMaximumWidth(150)
        self.edit_agent_name.setPlaceholderText("Tên Admin")

        row1.addWidget(lbl_name)
        row1.addWidget(self.edit_agent_name)

        # Connect Button
        self.btn_connect = QPushButton("⚡ Kết nối")
        self.btn_connect.setObjectName("btnConnect")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        row1.addWidget(self.btn_connect)

        # Leave Button
        self.btn_leave = QPushButton("⛔ Rời phòng")
        self.btn_leave.setObjectName("btnLeave")
        self.btn_leave.setCursor(Qt.PointingHandCursor)
        self.btn_leave.setEnabled(False)
        self.btn_leave.clicked.connect(self.sig_leave_requested.emit)
        row1.addWidget(self.btn_leave)

        # Greeting Button
        self.btn_greeting = QPushButton("👋 Gửi lời chào")
        self.btn_greeting.setObjectName("btnGreeting")
        self.btn_greeting.setCursor(Qt.PointingHandCursor)
        self.btn_greeting.setEnabled(False)
        self.btn_greeting.setToolTip("Gửi lời chào hoặc thông báo gia nhập phòng sau khi đã kết nối thành công")
        self.btn_greeting.clicked.connect(self.sig_greeting_requested.emit)
        row1.addWidget(self.btn_greeting)

        row1.addStretch()

        # Connection status badge
        self.lbl_status_badge = QLabel("⚪ Chưa kết nối")
        self.apply_badge_style("disconnected")
        row1.addWidget(self.lbl_status_badge)

        main_layout.addLayout(row1)

        # -----------------------------
        # Row 2: Session info (Agent ID, Token, Server URL)
        # -----------------------------
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        # Server URL
        lbl_server = QLabel("Server API:")
        lbl_server.setStyleSheet("color: #64748b; font-size: 12px;")
        self.edit_server_url = QLineEdit(DEFAULT_SERVER_URL)
        self.edit_server_url.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        self.edit_server_url.setMaximumWidth(260)

        row2.addWidget(lbl_server)
        row2.addWidget(self.edit_server_url)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #cbd5e1;")
        row2.addWidget(sep)

        # Agent ID
        self.lbl_agent_id = QLabel("Agent ID: <i>Chưa có</i>")
        self.lbl_agent_id.setStyleSheet("color: #475569; font-size: 13px;")
        row2.addWidget(self.lbl_agent_id)

        # Agent Token
        self.lbl_token = QLabel("Token: <i>Chưa có</i>")
        self.lbl_token.setStyleSheet("color: #475569; font-size: 13px;")
        row2.addWidget(self.lbl_token)

        self.btn_toggle_token = QToolButton()
        self.btn_toggle_token.setText("👁️")
        self.btn_toggle_token.setToolTip("Hiện / Ẩn Token")
        self.btn_toggle_token.setVisible(False)
        self.btn_toggle_token.clicked.connect(self.toggle_token_visibility)
        row2.addWidget(self.btn_toggle_token)

        self.btn_copy_token = QToolButton()
        self.btn_copy_token.setText("📋")
        self.btn_copy_token.setToolTip("Sao chép Agent Token")
        self.btn_copy_token.setVisible(False)
        self.btn_copy_token.clicked.connect(self.copy_token_to_clipboard)
        row2.addWidget(self.btn_copy_token)

        row2.addStretch()
        main_layout.addLayout(row2)

    def apply_badge_style(self, state: str):
        if state == "connected":
            self.lbl_status_badge.setText("🟢 Đã kết nối")
            bg = "#dcfce7" if not self.dark_mode else "rgba(34, 197, 94, 0.15)"
            color = "#15803d" if not self.dark_mode else "#4ade80"
            border = "#86efac" if not self.dark_mode else "transparent"
        elif state == "connecting":
            self.lbl_status_badge.setText("🟡 Đang kết nối...")
            bg = "#fef9c3" if not self.dark_mode else "rgba(234, 179, 8, 0.15)"
            color = "#a16207" if not self.dark_mode else "#facc15"
            border = "#fde047" if not self.dark_mode else "transparent"
        elif state == "error":
            self.lbl_status_badge.setText("🔴 Lỗi kết nối")
            bg = "#fee2e2" if not self.dark_mode else "rgba(239, 68, 68, 0.15)"
            color = "#b91c1c" if not self.dark_mode else "#f87171"
            border = "#fca5a5" if not self.dark_mode else "transparent"
        else:  # disconnected
            self.lbl_status_badge.setText("⚪ Chưa kết nối")
            bg = "#f1f5f9" if not self.dark_mode else "#26293b"
            color = "#64748b" if not self.dark_mode else "#94a3b8"
            border = "#cbd5e1" if not self.dark_mode else "transparent"

        self.lbl_status_badge.setStyleSheet(
            f"background-color: {bg}; color: {color}; border: 1px solid {border}; "
            "padding: 5px 12px; border-radius: 14px; font-weight: bold; font-size: 13px;"
        )

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        state = "connected" if self.is_connected else "disconnected"
        self.apply_badge_style(state)

    def on_connect_clicked(self):
        room_id = self.combo_room_id.currentText().strip()
        agent_name = self.edit_agent_name.text().strip() or "Admin"
        server_url = self.edit_server_url.text().strip() or DEFAULT_SERVER_URL

        if not room_id:
            return

        self.set_connecting_state()
        self.sig_connect_requested.emit(room_id, agent_name, server_url)

    def set_connecting_state(self):
        self.btn_connect.setEnabled(False)
        self.btn_leave.setEnabled(False)
        self.btn_greeting.setEnabled(False)
        self.combo_room_id.setEnabled(False)
        self.edit_agent_name.setEnabled(False)
        self.edit_server_url.setEnabled(False)
        self.apply_badge_style("connecting")

    def set_connected_state(self, agent_id: str, agent_token: str):
        self.is_connected = True
        self.agent_id = agent_id
        self.agent_token = agent_token

        self.btn_connect.setEnabled(False)
        self.btn_leave.setEnabled(True)
        self.btn_greeting.setEnabled(True)
        self.combo_room_id.setEnabled(False)
        self.edit_agent_name.setEnabled(False)
        self.edit_server_url.setEnabled(False)

        self.apply_badge_style("connected")

        self.lbl_agent_id.setText(f"Agent ID: <b style='color:#0284c7;'>{agent_id}</b>")
        self.btn_toggle_token.setVisible(True)
        self.btn_copy_token.setVisible(True)
        self._token_visible = False
        self.update_token_display()

        # Add room to history
        room_id = self.combo_room_id.currentText().strip()
        idx = self.combo_room_id.findText(room_id)
        if idx < 0:
            self.combo_room_id.insertItem(0, room_id)

    def set_disconnected_state(self):
        self.is_connected = False
        self.agent_id = ""
        self.agent_token = ""

        self.btn_connect.setEnabled(True)
        self.btn_leave.setEnabled(False)
        self.btn_greeting.setEnabled(False)
        self.combo_room_id.setEnabled(True)
        self.edit_agent_name.setEnabled(True)
        self.edit_server_url.setEnabled(True)

        self.apply_badge_style("disconnected")

        self.lbl_agent_id.setText("Agent ID: <i>Chưa có</i>")
        self.lbl_token.setText("Token: <i>Chưa có</i>")
        self.btn_toggle_token.setVisible(False)
        self.btn_copy_token.setVisible(False)

    def set_error_state(self, err_text: str):
        self.is_connected = False
        self.btn_connect.setEnabled(True)
        self.btn_leave.setEnabled(False)
        self.btn_greeting.setEnabled(False)
        self.combo_room_id.setEnabled(True)
        self.edit_agent_name.setEnabled(True)
        self.edit_server_url.setEnabled(True)

        self.apply_badge_style("error")

    def toggle_token_visibility(self):
        self._token_visible = not self._token_visible
        self.update_token_display()

    def update_token_display(self):
        if not self.agent_token:
            self.lbl_token.setText("Token: <i>Chưa có</i>")
            return

        token_color = "#7c3aed" if not self.dark_mode else "#a78bfa"
        if self._token_visible:
            self.lbl_token.setText(f"Token: <span style='color:{token_color};'>{self.agent_token}</span>")
            self.btn_toggle_token.setText("🙈")
        else:
            masked = self.agent_token[:6] + "..." + self.agent_token[-4:] if len(self.agent_token) > 10 else "******"
            self.lbl_token.setText(f"Token: <span style='color:{token_color};'>{masked}</span>")
            self.btn_toggle_token.setText("👁️")

    def copy_token_to_clipboard(self):
        if self.agent_token:
            QApplication.clipboard().setText(self.agent_token)

    def set_room_history(self, history: list):
        current = self.combo_room_id.currentText()
        self.combo_room_id.clear()
        for h in history:
            if h:
                self.combo_room_id.addItem(h)
        if current:
            self.combo_room_id.setEditText(current)
