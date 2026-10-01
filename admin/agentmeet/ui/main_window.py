"""Main Application Window for AgentMeet Admin Console with Light Theme, large fonts, and high stability."""

import sys
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QToolBar, QAction, QLabel, QCheckBox, QSpinBox,
    QMessageBox, QStatusBar, QApplication
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence

from agentmeet.config import (
    APP_NAME, APP_VERSION, SettingsManager, DEFAULT_ROOM_ID,
    DEFAULT_AGENT_NAME, DEFAULT_SERVER_URL
)
from agentmeet.models import ChatMessage, RoomStatus, AgentInfo
from agentmeet.api_client import AgentMeetClient
from agentmeet.workers import GenericTaskWorker, PollWorker

from agentmeet.ui.connection_bar import ConnectionBar
from agentmeet.ui.chat_widget import ChatWidget
from agentmeet.ui.agents_panel import AgentsPanel
from agentmeet.ui.status_panel import RoomStatusPanel
from agentmeet.ui.greeting_dialog import GreetingDialog
from agentmeet.ui.theme import LIGHT_THEME_QSS, DARK_THEME_QSS


class MainWindow(QMainWindow):
    """Cửa sổ chính của AgentMeet Admin Console."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1200, 780)
        self.setMinimumSize(900, 620)

        self.dark_mode = False  # Mặc định Light Theme theo yêu cầu
        self.settings = SettingsManager()
        self.client = AgentMeetClient(
            room_id=self.settings.get_last_room_id(),
            server_url=self.settings.get_server_url()
        )

        self.agent_id: str = ""
        self.agent_token: str = ""
        self.poll_worker: Optional[PollWorker] = None
        self.active_workers: List[GenericTaskWorker] = []

        self.init_ui()
        self.init_menubar()
        self.init_toolbar()
        self.init_statusbar()
        self.load_initial_settings()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # -----------------------------
        # Thanh kết nối trên cùng
        # -----------------------------
        self.conn_bar = ConnectionBar(dark_mode=self.dark_mode)
        self.conn_bar.sig_connect_requested.connect(self.on_connect_requested)
        self.conn_bar.sig_leave_requested.connect(self.on_leave_requested)
        self.conn_bar.sig_greeting_requested.connect(self.on_open_greeting_dialog)
        main_layout.addWidget(self.conn_bar)

        # -----------------------------
        # Splitter chính: Chat Widget (trái) + Sidebar Tabs (phải)
        # -----------------------------
        self.splitter = QSplitter(Qt.Horizontal)

        # Trái: Chat Widget (Chữ to, rõ nét, có zoom)
        self.chat_widget = ChatWidget(dark_mode=self.dark_mode)
        self.chat_widget.sig_send_message.connect(self.on_send_message_requested)
        self.splitter.addWidget(self.chat_widget)

        # Phải: Sidebar Tabs
        self.tabs_sidebar = QTabWidget()
        self.tabs_sidebar.setMinimumWidth(300)

        # Tab 1: Thành viên phòng (Agents)
        self.agents_panel = AgentsPanel(dark_mode=self.dark_mode)
        self.agents_panel.sig_fetch_agents_requested.connect(self.on_fetch_agents_requested)
        self.agents_panel.sig_filter_agent_selected.connect(self.on_filter_by_agent)
        self.agents_panel.sig_mention_agent_requested.connect(self.on_mention_agent)
        self.tabs_sidebar.addTab(self.agents_panel, "👥 Thành viên")

        # Tab 2: Trạng thái phòng (Status)
        self.status_panel = RoomStatusPanel(dark_mode=self.dark_mode)
        self.status_panel.sig_fetch_status_requested.connect(self.on_fetch_status_requested)
        self.tabs_sidebar.addTab(self.status_panel, "📊 Trạng thái")

        self.splitter.addWidget(self.tabs_sidebar)
        self.splitter.setStretchFactor(0, 7)  # Chat chiếm 70%
        self.splitter.setStretchFactor(1, 3)  # Sidebar chiếm 30%

        main_layout.addWidget(self.splitter, stretch=1)

    def init_menubar(self):
        menubar = self.menuBar()

        # File Menu
        menu_file = menubar.addMenu("📁 Tệp")

        act_export = QAction("💾 Xuất Transcript...", self)
        act_export.triggered.connect(self.chat_widget.export_chat)
        menu_file.addAction(act_export)

        menu_file.addSeparator()

        act_exit = QAction("❌ Thoát", self)
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Fetch Menu ("fetch ,v,v nhiều tính năng")
        menu_fetch = menubar.addMenu("⚡ Dữ liệu & Fetch")

        act_fetch_all = QAction("📥 Tải Transcript Gần Nhất (/transcript)", self)
        act_fetch_all.triggered.connect(lambda: self.on_fetch_transcript_requested(limit=100))
        menu_fetch.addAction(act_fetch_all)

        act_fetch_status = QAction("📊 Lấy Trạng Thái Phòng (/status)", self)
        act_fetch_status.triggered.connect(self.on_fetch_status_requested)
        menu_fetch.addAction(act_fetch_status)

        act_fetch_agents = QAction("👥 Cập Nhật Danh Sách Agents", self)
        act_fetch_agents.triggered.connect(self.on_fetch_agents_requested)
        menu_fetch.addAction(act_fetch_agents)

        act_read_new = QAction("🔄 Đọc Tin Nhắn Mới Thủ Công (/read)", self)
        act_read_new.triggered.connect(self.on_manual_read_requested)
        menu_fetch.addAction(act_read_new)

        # Actions Menu
        menu_actions = menubar.addMenu("🛠️ Thao tác")

        self.act_greeting = QAction("👋 Gửi Lời Chào Vào Phòng...", self)
        self.act_greeting.setEnabled(False)
        self.act_greeting.triggered.connect(self.on_open_greeting_dialog)
        menu_actions.addAction(self.act_greeting)

        act_clear = QAction("🗑️ Xóa Màn Hình Transcript", self)
        act_clear.triggered.connect(self.chat_widget.clear_display)
        menu_actions.addAction(act_clear)

        # View Menu (Theme & Font zoom)
        menu_view = menubar.addMenu("👁️ Giao diện")

        self.act_toggle_theme = QAction("🌓 Chuyển Giao Diện Tối / Sáng", self)
        self.act_toggle_theme.triggered.connect(self.toggle_theme)
        menu_view.addAction(self.act_toggle_theme)

        menu_view.addSeparator()

        act_zoom_in = QAction("🔍 Phóng To Chữ (Ctrl +)", self)
        act_zoom_in.setShortcut(QKeySequence("Ctrl+=" ))
        act_zoom_in.triggered.connect(self.chat_widget.zoom_in)
        menu_view.addAction(act_zoom_in)

        act_zoom_out = QAction("🔍 Thu Nhỏ Chữ (Ctrl -)", self)
        act_zoom_out.setShortcut(QKeySequence("Ctrl+-" ))
        act_zoom_out.triggered.connect(self.chat_widget.zoom_out)
        menu_view.addAction(act_zoom_out)

        # Help Menu
        menu_help = menubar.addMenu("❓ Trợ giúp")
        act_about = QAction("Về AgentMeet Console...", self)
        act_about.triggered.connect(self.show_about_dialog)
        menu_help.addAction(act_about)

    def init_toolbar(self):
        toolbar = QToolBar("Thanh công cụ tác vụ")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Fetch Transcript
        act_fetch = toolbar.addAction("📥 Fetch Transcript")
        act_fetch.setToolTip("Tải các tin nhắn gần nhất từ phòng họp")
        act_fetch.triggered.connect(lambda: self.on_fetch_transcript_requested(limit=100))

        # Fetch Status
        act_status = toolbar.addAction("📊 Fetch Status")
        act_status.setToolTip("Cập nhật số lượng tin nhắn và trạng thái phòng")
        act_status.triggered.connect(self.on_fetch_status_requested)

        # Fetch Agents
        act_agents = toolbar.addAction("👥 Fetch Agents")
        act_agents.setToolTip("Lấy danh sách thành viên hiện tại trong phòng")
        act_agents.triggered.connect(self.on_fetch_agents_requested)

        toolbar.addSeparator()

        # Manual Refresh / Read
        act_refresh = toolbar.addAction("🔄 Refresh")
        act_refresh.setToolTip("Kiểm tra tin nhắn mới ngay lập tức")
        act_refresh.triggered.connect(self.on_manual_read_requested)

        toolbar.addSeparator()

        # Auto Poll Controls
        self.chk_auto_poll = QCheckBox("Tự động đọc tin mới")
        self.chk_auto_poll.setChecked(self.settings.get_auto_poll())
        self.chk_auto_poll.toggled.connect(self.on_auto_poll_toggled)
        toolbar.addWidget(self.chk_auto_poll)

        toolbar.addWidget(QLabel(" mỗi "))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setValue(int(self.settings.get_poll_interval()))
        self.spin_interval.setSuffix(" s")
        self.spin_interval.valueChanged.connect(self.on_poll_interval_changed)
        toolbar.addWidget(self.spin_interval)

        toolbar.addSeparator()

        # Theme Switcher button
        act_theme = toolbar.addAction("🌓 Đổi Theme")
        act_theme.setToolTip("Chuyển đổi giữa giao diện Sáng (Light) và Tối (Dark)")
        act_theme.triggered.connect(self.toggle_theme)

    def init_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.lbl_sb_room = QLabel("Phòng: —")
        self.lbl_sb_room.setStyleSheet("color: #0284c7; font-weight: bold; margin-right: 15px; font-size: 13px;")
        self.statusbar.addPermanentWidget(self.lbl_sb_room)

        self.lbl_sb_count = QLabel("Tổng tin nhắn: 0")
        self.lbl_sb_count.setStyleSheet("color: #64748b; margin-right: 15px; font-size: 13px;")
        self.statusbar.addPermanentWidget(self.lbl_sb_count)

        self.statusbar.showMessage("Sẵn sàng.", 5000)

    def load_initial_settings(self):
        history = self.settings.get_room_history()
        self.conn_bar.set_room_history(history)
        self.conn_bar.edit_agent_name.setText(self.settings.get_agent_name())
        self.conn_bar.edit_server_url.setText(self.settings.get_server_url())

        # Pre-fetch status and agents in background to display immediately
        self.client.update_config(self.settings.get_last_room_id(), self.settings.get_server_url())
        self.lbl_sb_room.setText(f"Phòng: {self.client.room_id}")
        QTimer.singleShot(400, self.on_fetch_status_requested)
        QTimer.singleShot(600, self.on_fetch_agents_requested)
        QTimer.singleShot(800, lambda: self.on_fetch_transcript_requested(limit=40))

    # =============================================================
    # Theme Toggle (Sáng / Tối)
    # =============================================================

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        qss = DARK_THEME_QSS if self.dark_mode else LIGHT_THEME_QSS
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

        self.conn_bar.set_dark_mode(self.dark_mode)
        self.chat_widget.set_dark_mode(self.dark_mode)
        self.agents_panel.set_dark_mode(self.dark_mode)
        self.status_panel.set_dark_mode(self.dark_mode)

        room_color = "#38bdf8" if self.dark_mode else "#0284c7"
        self.lbl_sb_room.setStyleSheet(f"color: {room_color}; font-weight: bold; margin-right: 15px; font-size: 13px;")

        theme_name = "Tối" if self.dark_mode else "Sáng"
        self.statusbar.showMessage(f"Đã chuyển sang giao diện {theme_name}.", 3000)

    # =============================================================
    # Worker Lifecycle Management (Chống rò rỉ bộ nhớ & ổn định cao)
    # =============================================================

    def _spawn_worker(self, fn, *args, **kwargs) -> GenericTaskWorker:
        worker = GenericTaskWorker(fn, *args, **kwargs)
        self.active_workers.append(worker)
        worker.sig_finished.connect(lambda: self._cleanup_worker(worker))
        return worker

    def _cleanup_worker(self, worker: GenericTaskWorker):
        if worker in self.active_workers:
            self.active_workers.remove(worker)

    # =============================================================
    # Connection Handlers (Join / Leave)
    # =============================================================

    def on_connect_requested(self, room_id: str, agent_name: str, server_url: str):
        self.client.update_config(room_id, server_url)
        self.settings.set_last_room_id(room_id)
        self.settings.set_agent_name(agent_name)
        self.settings.set_server_url(server_url)

        self.chat_widget.set_session_info(agent_name, "")
        self.lbl_sb_room.setText(f"Phòng: {room_id}")
        self.statusbar.showMessage(f"Đang kết nối phòng {room_id}...", 5000)

        worker = self._spawn_worker(self.client.join_room, agent_name=agent_name)
        worker.sig_success.connect(lambda res: self.handle_join_success(res, agent_name))
        worker.sig_error.connect(self.handle_join_error)
        worker.start()

    def handle_join_success(self, result, agent_name: str):
        agent_id, agent_token, transcript = result
        self.agent_id = agent_id
        self.agent_token = agent_token

        self.conn_bar.set_connected_state(agent_id, agent_token)
        self.act_greeting.setEnabled(True)
        self.chat_widget.set_session_info(agent_name, agent_id)
        self.chat_widget.set_connected(True)

        self.chat_widget.append_system_notice(
            f"🎉 Đã kết nối thành công phòng họp '{self.client.room_id}' với vai trò: {agent_name} (ID: {agent_id})."
        )
        self.chat_widget.append_system_notice(
            "👉 Lưu ý: Bạn có thể bấm nút '👋 Gửi lời chào' ở trên để chào hỏi các agent khi sẵn sàng."
        )

        # Nạp transcript ban đầu nếu có
        if transcript:
            parsed_msgs = [ChatMessage.from_dict(m, agent_name, agent_id) for m in transcript]
            for msg in parsed_msgs:
                self.chat_widget.add_message(msg)

        # Cập nhật danh sách thành viên và trạng thái
        self.on_fetch_status_requested()
        self.on_fetch_agents_requested()

        # Bật auto poll
        self.start_poll_worker()

        self.statusbar.showMessage("Đã kết nối phòng họp thành công!", 4000)

    def handle_join_error(self, err_str: str):
        self.conn_bar.set_error_state(err_str)
        self.chat_widget.append_error_notice(f"Lỗi tham gia phòng họp: {err_str}")
        self.statusbar.showMessage(f"Lỗi kết nối: {err_str}", 6000)

    def on_leave_requested(self):
        if not self.agent_token:
            return

        self.stop_poll_worker()
        token = self.agent_token
        self.agent_token = ""
        self.agent_id = ""

        self.conn_bar.set_disconnected_state()
        self.act_greeting.setEnabled(False)
        self.chat_widget.set_connected(False)
        self.chat_widget.append_system_notice("Đã ngắt kết nối và rời phòng họp.")

        worker = self._spawn_worker(self.client.leave_room, agent_token=token)
        worker.start()

    # =============================================================
    # Greeting Feature (Dedicated Manual Greeting Button)
    # =============================================================

    def on_open_greeting_dialog(self):
        """Mở hộp thoại gửi lời chào theo yêu cầu người dùng."""
        if not self.agent_token:
            QMessageBox.warning(self, "Chưa kết nối", "Vui lòng kết nối vào phòng trước khi gửi lời chào.")
            return

        agent_name = self.conn_bar.edit_agent_name.text().strip() or "Admin"
        dlg = GreetingDialog(self, current_agent_name=agent_name)
        dlg.sig_send_greeting.connect(self.on_send_message_requested)
        dlg.exec_()

    # =============================================================
    # Message Sending
    # =============================================================

    def on_send_message_requested(self, content: str):
        if not self.agent_token:
            QMessageBox.warning(self, "Chưa kết nối", "Bạn cần kết nối vào phòng trước khi gửi tin nhắn.")
            return

        agent_name = self.conn_bar.edit_agent_name.text().strip() or "Admin"

        local_msg = ChatMessage(
            agent_name=agent_name,
            agent_id=self.agent_id,
            content=content,
            is_self=True,
            timestamp=""
        )
        self.chat_widget.add_message(local_msg)

        worker = self._spawn_worker(
            self.client.send_message,
            agent_token=self.agent_token,
            agent_name=agent_name,
            content=content
        )
        worker.sig_error.connect(lambda err: self.chat_widget.append_error_notice(f"Gửi tin nhắn thất bại: {err}"))
        worker.start()

    # =============================================================
    # Fetch Features (Transcript, Status, Agents, Read)
    # =============================================================

    def on_fetch_transcript_requested(self, limit: int = 100):
        """Tải tin nhắn từ /transcript."""
        room_id = self.conn_bar.combo_room_id.currentText().strip()
        self.client.update_config(room_id)
        self.statusbar.showMessage("Đang tải dữ liệu transcript...", 3000)

        worker = self._spawn_worker(self.client.fetch_transcript, limit=limit, offset=0)
        worker.sig_success.connect(self.handle_fetch_transcript_success)
        worker.sig_error.connect(lambda err: self.chat_widget.append_error_notice(f"Lỗi fetch transcript: {err}"))
        worker.start()

    def handle_fetch_transcript_success(self, data: Dict[str, Any]):
        raw_msgs = data.get("messages", [])
        total = data.get("total_messages", len(raw_msgs))
        self.lbl_sb_count.setText(f"Tổng tin nhắn: {total}")

        raw_agents = data.get("agents", [])
        if raw_agents:
            agents = [AgentInfo.from_dict(a) for a in raw_agents if isinstance(a, dict)]
            self.agents_panel.set_agents(agents)

        agent_name = self.conn_bar.edit_agent_name.text().strip() or "Admin"
        parsed_msgs = [ChatMessage.from_dict(m, agent_name, self.agent_id) for m in raw_msgs]
        self.chat_widget.set_messages(parsed_msgs)

        self.statusbar.showMessage(f"Đã tải {len(parsed_msgs)}/{total} tin nhắn từ phòng.", 4000)

    def on_fetch_status_requested(self):
        """Lấy thông tin trạng thái phòng từ /status."""
        room_id = self.conn_bar.combo_room_id.currentText().strip()
        self.client.update_config(room_id)

        worker = self._spawn_worker(self.client.fetch_status)
        worker.sig_success.connect(self.handle_fetch_status_success)
        worker.sig_error.connect(lambda err: self.statusbar.showMessage(f"Lỗi fetch status: {err}", 5000))
        worker.start()

    def handle_fetch_status_success(self, status: RoomStatus):
        self.status_panel.update_status(status)
        self.lbl_sb_count.setText(f"Tổng tin nhắn: {status.message_count}/{status.max_messages}")

    def on_fetch_agents_requested(self):
        """Lấy danh sách các agent tham gia phòng."""
        room_id = self.conn_bar.combo_room_id.currentText().strip()
        self.client.update_config(room_id)

        worker = self._spawn_worker(self.client.fetch_agents)
        worker.sig_success.connect(lambda agents: self.agents_panel.set_agents(agents))
        worker.sig_error.connect(lambda err: self.statusbar.showMessage(f"Lỗi fetch agents: {err}", 5000))
        worker.start()

    def on_manual_read_requested(self):
        """Đọc tin nhắn mới thủ công từ /read."""
        if not self.agent_token:
            self.on_fetch_transcript_requested(limit=40)
            return

        worker = self._spawn_worker(self.client.read_new_messages, agent_token=self.agent_token)
        worker.sig_success.connect(self.handle_new_messages)
        worker.sig_error.connect(lambda err: self.statusbar.showMessage(f"Lỗi đọc tin nhắn mới: {err}", 5000))
        worker.start()

    def handle_new_messages(self, messages_data: list):
        if not messages_data:
            return
        agent_name = self.conn_bar.edit_agent_name.text().strip() or "Admin"
        for m in messages_data:
            msg = ChatMessage.from_dict(m, agent_name, self.agent_id)
            self.chat_widget.add_message(msg)

    # =============================================================
    # Polling & Worker Lifecycle
    # =============================================================

    def start_poll_worker(self):
        self.stop_poll_worker()
        if not self.agent_token:
            return

        interval = float(self.spin_interval.value())
        self.poll_worker = PollWorker(self.client, self.agent_token, interval=interval)
        self.poll_worker.sig_new_messages.connect(self.handle_new_messages)
        if not self.chk_auto_poll.isChecked():
            self.poll_worker.pause()
        self.poll_worker.start()

    def stop_poll_worker(self):
        if self.poll_worker:
            self.poll_worker.stop()
            self.poll_worker = None

    def on_auto_poll_toggled(self, checked: bool):
        self.settings.set_auto_poll(checked)
        if self.poll_worker:
            if checked:
                self.poll_worker.resume()
            else:
                self.poll_worker.pause()

    def on_poll_interval_changed(self, val: int):
        self.settings.set_poll_interval(float(val))
        if self.poll_worker:
            self.poll_worker.set_interval(float(val))

    # =============================================================
    # Sidebar Interactivity
    # =============================================================

    def on_filter_by_agent(self, agent_name: str):
        idx = self.chat_widget.combo_agent_filter.findData(agent_name)
        if idx >= 0:
            self.chat_widget.combo_agent_filter.setCurrentIndex(idx)
        else:
            self.chat_widget.update_agent_filter_combo(agent_name)
            idx = self.chat_widget.combo_agent_filter.findData(agent_name)
            if idx >= 0:
                self.chat_widget.combo_agent_filter.setCurrentIndex(idx)

    def on_mention_agent(self, mention_tag: str):
        current = self.chat_widget.input_text.toPlainText()
        self.chat_widget.input_text.setPlainText(current + mention_tag)
        self.chat_widget.input_text.setFocus()

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            f"Về {APP_NAME}",
            f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
            "<p>Ứng dụng quản trị và giám sát phòng họp đa Agent AgentMeet.</p>"
            "<p><b>Điểm cải tiến mới:</b></p>"
            "<ul>"
            "<li>Giao diện <b>Light Theme</b> trang nhã, độ tương phản cao, chuyển đổi Sáng/Tối linh hoạt.</li>"
            "<li>Chữ to rõ ràng hơn, hỗ trợ tăng giảm cỡ chữ nhanh (A+ / A- hoặc Ctrl+/Ctrl-).</li>"
            "<li>Cơ chế chống trùng lặp tin nhắn 100%, bảo đảm ổn định tối đa.</li>"
            "<li>Nhập Room ID tự do, lưu lịch sử kết nối.</li>"
            "<li>Nút gửi lời chào chủ động sau khi kết nối.</li>"
            "<li>Bộ công cụ Fetch toàn diện: Transcript, Trạng thái phòng, Thành viên.</li>"
            "</ul>"
            "<p>Tác giả: <b>KBC2</b></p>"
        )

    def closeEvent(self, event):
        """Dọn dẹp session và worker an toàn khi đóng ứng dụng."""
        self.stop_poll_worker()
        for worker in list(self.active_workers):
            worker.abort()
            worker.quit()
        if self.agent_token:
            try:
                self.client.leave_room(self.agent_token)
            except Exception:
                pass
        event.accept()
