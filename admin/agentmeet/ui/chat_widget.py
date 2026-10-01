"""Modern rich-text chat widget with markdown/JSON styling, search, font-zoom, and light theme support."""

import html
import re
import json
from datetime import datetime
from typing import List, Optional, Set

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QPlainTextEdit, QPushButton, QLineEdit, QComboBox,
    QCheckBox, QLabel, QFileDialog, QMessageBox, QFrame,
    QToolButton
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QTextCursor, QFont

from agentmeet.models import ChatMessage
from agentmeet.ui.theme import get_agent_color_style


def format_message_content_to_html(raw_content: str, dark_mode: bool = False, font_size: int = 15) -> str:
    """
    Chuyển đổi nội dung tin nhắn dạng Markdown/JSON/Plain text sang HTML hiển thị đẹp mắt,
    hỗ trợ cỡ chữ tùy chỉnh và chế độ Light/Dark theme.
    """
    if not raw_content:
        return ""

    text = html.escape(raw_content)

    # 1. Khối mã ```...```
    code_bg = "#1e293b" if dark_mode else "#f8fafc"
    code_border = "#334155" if dark_mode else "#cbd5e1"
    code_text = "#e2e8f0" if dark_mode else "#0f172a"

    def replace_code_block(match):
        code_body = match.group(1)
        return (
            f'<div style="background-color: {code_bg}; border: 1px solid {code_border}; '
            f'border-radius: 6px; padding: 10px 14px; margin: 8px 0; font-family: Consolas, monospace; '
            f'font-size: {font_size - 1}px; color: {code_text}; white-space: pre-wrap; line-height: 1.4;">'
            f'{code_body}</div>'
        )

    text = re.sub(r'```(?:[a-zA-Z0-9_\-]+)?\n?(.*?)```', replace_code_block, text, flags=re.DOTALL)

    # 2. Inline code `code`
    inline_bg = "#27273a" if dark_mode else "#f1f5f9"
    inline_text = "#f43f5e" if dark_mode else "#e11d48"
    text = re.sub(
        r'`([^`\n]+)`',
        rf'<code style="background-color: {inline_bg}; color: {inline_text}; padding: 2px 6px; '
        rf'border-radius: 4px; font-family: Consolas, monospace; font-size: {font_size - 1}px; font-weight: 600;">\1</code>',
        text
    )

    # 3. JSON nhúng trong tin nhắn
    json_bg = "#0f172a" if dark_mode else "#f0fdf4"
    json_border = "#38bdf8" if dark_mode else "#059669"
    json_color = "#7dd3fc" if dark_mode else "#065f46"

    def format_json_match(match):
        raw_json_str = match.group(0)
        unescaped = html.unescape(raw_json_str)
        try:
            parsed = json.loads(unescaped)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            escaped_pretty = html.escape(pretty)
            return (
                f'<div style="background-color: {json_bg}; border-left: 4px solid {json_border}; '
                f'border-radius: 5px; padding: 8px 12px; margin: 8px 0; font-family: Consolas, monospace; '
                f'font-size: {font_size - 2}px; color: {json_color}; white-space: pre-wrap; line-height: 1.4;">'
                f'<b>📋 JSON Data:</b><br>{escaped_pretty}</div>'
            )
        except Exception:
            return raw_json_str

    text = re.sub(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', format_json_match, text)

    # 4. Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b style="color: inherit;">\1</b>', text)

    # 5. Italic *text*
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<i>\1</i>', text)

    # 6. Mentions @Name
    mention_color = "#0284c7" if not dark_mode else "#38bdf8"
    mention_bg = "rgba(2, 132, 199, 0.12)" if not dark_mode else "rgba(56, 189, 248, 0.15)"
    text = re.sub(
        r'(@[a-zA-Z0-9_.\-\(\)\s]+?)(?=\s|$|[.,:;!?])',
        rf'<span style="color: {mention_color}; font-weight: bold; background-color: {mention_bg}; '
        r'padding: 2px 6px; border-radius: 4px;">\1</span>',
        text
    )

    # 7. Protocol tags [hello], [lead], [task], [vote], v.v.
    tag_colors = {
        "hello": ("#10b981", "#ffffff"),
        "lead": ("#f59e0b", "#ffffff"),
        "lead-election": ("#f59e0b", "#ffffff"),
        "task": ("#6366f1", "#ffffff"),
        "vote": ("#ec4899", "#ffffff"),
        "admin": ("#ef4444", "#ffffff"),
        "ack": ("#06b6d4", "#ffffff"),
    }

    def replace_bracket_tag(m):
        raw_tag = m.group(1).lower()
        bg, fg = tag_colors.get(raw_tag, ("#8b5cf6", "#ffffff"))
        return (
            f'<span style="background-color: {bg}; color: {fg}; '
            f'padding: 2px 7px; border-radius: 4px; font-size: {font_size - 3}px; font-weight: bold;">[{m.group(1)}]</span>'
        )

    text = re.sub(r'\[([a-zA-Z0-9_\-]+)\]', replace_bracket_tag, text)

    # 8. Newlines
    text = text.replace('\n', '<br>')

    return text


class ChatMessageInput(QPlainTextEdit):
    """Ô soạn thảo tin nhắn phím tắt Ctrl+Enter gửi đi."""

    sig_send_triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Nhập tin nhắn... (Nhấn Ctrl + Enter để gửi)")
        self.setMaximumHeight(90)
        self.setMinimumHeight(60)
        # Font chữ to, dễ đọc
        f = self.font()
        f.setPointSize(11)
        self.setFont(f)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ControlModifier:
                self.sig_send_triggered.emit()
                return
        super().keyPressEvent(event)


class ChatWidget(QWidget):
    """
    Widget hiển thị transcript trò chuyện:
    - Giao diện Light theme mượt mà, độ tương phản cao, chữ to rõ
    - Tự động lọc trùng lặp tin nhắn 100% (seen_message_keys)
    - Tăng/giảm kích thước chữ trực quan (Font Zoom)
    - Tìm kiếm và lọc theo Agent
    - Xuất file transcript (.txt / .json)
    """

    sig_send_message = pyqtSignal(str)

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.messages: List[ChatMessage] = []
        self.seen_keys: Set[str] = set()

        self.current_agent_name = "Admin"
        self.current_agent_id = ""
        self.filter_agent = "all"
        self.filter_keyword = ""
        self.chat_font_size = 15  # Cỡ chữ to hơn theo yêu cầu

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # -----------------------------
        # Toolbar: Search, Filter, Font Zoom, Export, Clear
        # -----------------------------
        bar_layout = QHBoxLayout()
        bar_layout.setSpacing(6)

        # Search box
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Tìm từ khóa...")
        self.edit_search.textChanged.connect(self.on_search_changed)
        bar_layout.addWidget(self.edit_search, stretch=2)

        # Filter by agent
        bar_layout.addWidget(QLabel("Lọc:"))
        self.combo_agent_filter = QComboBox()
        self.combo_agent_filter.addItem("Tất cả thành viên", "all")
        self.combo_agent_filter.currentIndexChanged.connect(self.on_agent_filter_changed)
        bar_layout.addWidget(self.combo_agent_filter, stretch=1)

        # Font Zoom Controls ("chữ to hơn")
        btn_zoom_out = QToolButton()
        btn_zoom_out.setText("A-")
        btn_zoom_out.setToolTip("Giảm cỡ chữ chat")
        btn_zoom_out.clicked.connect(self.zoom_out)
        bar_layout.addWidget(btn_zoom_out)

        self.lbl_font_size = QLabel(f"{self.chat_font_size}px")
        self.lbl_font_size.setStyleSheet("font-weight: bold; color: #64748b; font-size: 12px;")
        bar_layout.addWidget(self.lbl_font_size)

        btn_zoom_in = QToolButton()
        btn_zoom_in.setText("A+")
        btn_zoom_in.setToolTip("Tăng cỡ chữ chat (Chữ to hơn)")
        btn_zoom_in.clicked.connect(self.zoom_in)
        bar_layout.addWidget(btn_zoom_in)

        # Auto-scroll
        self.chk_auto_scroll = QCheckBox("Tự cuộn")
        self.chk_auto_scroll.setChecked(True)
        bar_layout.addWidget(self.chk_auto_scroll)

        # Export & Clear
        self.btn_export = QPushButton("💾 Xuất")
        self.btn_export.setToolTip("Xuất lịch sử chat ra file .txt hoặc .json")
        self.btn_export.clicked.connect(self.export_chat)
        bar_layout.addWidget(self.btn_export)

        self.btn_clear = QPushButton("🗑️ Xóa")
        self.btn_clear.setToolTip("Xóa màn hình transcript hiện tại")
        self.btn_clear.clicked.connect(self.clear_display)
        bar_layout.addWidget(self.btn_clear)

        layout.addLayout(bar_layout)

        # -----------------------------
        # Vùng hiển thị Chat (QTextBrowser)
        # -----------------------------
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.apply_browser_style()
        layout.addWidget(self.browser, stretch=1)

        # -----------------------------
        # Vùng soạn tin nhắn & nút Gửi
        # -----------------------------
        input_box = QHBoxLayout()
        input_box.setSpacing(8)

        self.input_text = ChatMessageInput()
        self.input_text.sig_send_triggered.connect(self.on_send_clicked)
        input_box.addWidget(self.input_text, stretch=1)

        btn_vbox = QVBoxLayout()
        self.btn_send = QPushButton("Gửi ↵\nCtrl+Enter")
        self.btn_send.setObjectName("btnSend")
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setMinimumHeight(60)
        self.btn_send.setMinimumWidth(110)
        self.btn_send.setEnabled(False)
        self.btn_send.clicked.connect(self.on_send_clicked)
        btn_vbox.addWidget(self.btn_send)

        input_box.addLayout(btn_vbox)
        layout.addLayout(input_box)

    def apply_browser_style(self):
        if not self.dark_mode:
            self.browser.setStyleSheet(
                "background-color: #f8fafc; border: 1px solid #cbd5e1; "
                "border-radius: 8px; padding: 12px;"
            )
        else:
            self.browser.setStyleSheet(
                "background-color: #141520; border: 1px solid #282a3d; "
                "border-radius: 8px; padding: 12px;"
            )

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        self.apply_browser_style()
        self.rerender_all()

    def zoom_in(self):
        if self.chat_font_size < 26:
            self.chat_font_size += 1
            self.lbl_font_size.setText(f"{self.chat_font_size}px")
            self.rerender_all()

    def zoom_out(self):
        if self.chat_font_size > 12:
            self.chat_font_size -= 1
            self.lbl_font_size.setText(f"{self.chat_font_size}px")
            self.rerender_all()

    def set_session_info(self, agent_name: str, agent_id: str):
        self.current_agent_name = agent_name
        self.current_agent_id = agent_id

    def set_connected(self, connected: bool):
        self.btn_send.setEnabled(connected)
        if connected:
            self.input_text.setPlaceholderText("Nhập tin nhắn... (Nhấn Ctrl + Enter để gửi)")
        else:
            self.input_text.setPlaceholderText("Hãy kết nối phòng để gửi tin nhắn...")

    # =============================================================
    # Message Handling & Deduplication (Ổn định 100%)
    # =============================================================

    def _get_message_key(self, msg: ChatMessage) -> str:
        """Tạo khóa định danh duy nhất để chống trùng lặp tin nhắn."""
        if msg.message_id is not None:
            return f"id_{msg.message_id}"
        # Fallback key cho tin nhắn tự gửi hoặc thông báo
        return f"content_{msg.agent_name}_{msg.timestamp}_{hash(msg.content)}"

    def add_message(self, message: ChatMessage):
        """Thêm tin nhắn mới có kiểm tra chống trùng lặp."""
        key = self._get_message_key(message)
        if key in self.seen_keys:
            return

        self.seen_keys.add(key)

        if self.current_agent_name and message.agent_name.strip().lower() == self.current_agent_name.strip().lower():
            message.is_self = True

        self.messages.append(message)
        self.update_agent_filter_combo(message.agent_name)

        if self.matches_filter(message):
            self.append_message_html(message)

    def set_messages(self, messages: List[ChatMessage]):
        """Cập nhật toàn bộ danh sách tin nhắn sau khi fetch transcript."""
        self.messages = []
        self.seen_keys.clear()

        for m in messages:
            key = self._get_message_key(m)
            if key in self.seen_keys:
                continue
            self.seen_keys.add(key)

            if self.current_agent_name and m.agent_name.strip().lower() == self.current_agent_name.strip().lower():
                m.is_self = True
            self.messages.append(m)
            self.update_agent_filter_combo(m.agent_name)

        self.rerender_all()

    def append_system_notice(self, text: str):
        msg = ChatMessage(agent_name="Hệ thống", content=text, is_system=True, timestamp=datetime.now().isoformat())
        self.add_message(msg)

    def append_error_notice(self, text: str):
        msg = ChatMessage(agent_name="Lỗi", content=text, is_error=True, timestamp=datetime.now().isoformat())
        self.add_message(msg)

    # =============================================================
    # HTML Rendering (Light Theme & Dark Theme)
    # =============================================================

    def render_message_html_block(self, msg: ChatMessage) -> str:
        time_str = msg.display_time()
        time_html = f"<span style='color: #64748b; font-size: {self.chat_font_size - 3}px; margin-left: 8px;'>{time_str}</span>" if time_str else ""
        mid_html = f"<span style='color: #94a3b8; font-size: {self.chat_font_size - 4}px; font-weight: bold; margin-right: 6px;'>#{msg.message_id}</span>" if msg.message_id else ""

        if msg.is_error:
            bg = "#fef2f2" if not self.dark_mode else "rgba(239, 68, 68, 0.12)"
            text_color = "#991b1b" if not self.dark_mode else "#fca5a5"
            return (
                f'<div style="background-color: {bg}; border-left: 4px solid #ef4444; border: 1px solid #fecaca; '
                f'border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; color: {text_color}; font-size: {self.chat_font_size}px;">'
                f'<b>⚠️ [LỖI]</b> {html.escape(msg.content)} {time_html}</div>'
            )

        if msg.is_system:
            bg = "#f1f5f9" if not self.dark_mode else "rgba(148, 163, 184, 0.08)"
            text_color = "#475569" if not self.dark_mode else "#94a3b8"
            return (
                f'<div style="background-color: {bg}; border: 1px dashed #cbd5e1; '
                f'border-radius: 6px; padding: 8px 14px; margin-bottom: 10px; color: {text_color}; font-size: {self.chat_font_size - 1}px;">'
                f'<b>ℹ️ [HỆ THỐNG]</b> {html.escape(msg.content)} {time_html}</div>'
            )

        style = get_agent_color_style(msg.agent_name, msg.is_self, self.dark_mode)
        name_color = style["name"]
        card_bg = style["bg"]
        card_border = style["border"]
        box_border = style.get("card_border", "#e2e8f0")

        self_badge = ""
        if msg.is_self:
            self_badge = f" <span style='background-color: #2563eb; color: #ffffff; padding: 2px 7px; border-radius: 10px; font-size: {self.chat_font_size - 4}px; font-weight: bold;'>BẠN (ADMIN)</span>"

        agent_id_pill = ""
        if msg.agent_id:
            agent_id_pill = f"<span style='color: #64748b; font-size: {self.chat_font_size - 4}px; margin-left: 4px;'>({html.escape(msg.agent_id)})</span>"

        formatted_body = format_message_content_to_html(msg.content, self.dark_mode, self.chat_font_size)

        # Style card có shadow nhẹ và border đẹp
        shadow_style = "box-shadow: 0 1px 3px rgba(0,0,0,0.06);" if not self.dark_mode else ""
        text_color = "#0f172a" if not self.dark_mode else "#e2e8f0"

        return (
            f'<div style="background-color: {card_bg}; border-left: 5px solid {card_border}; '
            f'border: 1px solid {box_border}; border-left-width: 5px; {shadow_style} '
            f'border-radius: 8px; padding: 10px 16px; margin-bottom: 12px;">'
            f'<div style="margin-bottom: 6px;">{mid_html}'
            f'<b style="color: {name_color}; font-size: {self.chat_font_size + 1}px;">{html.escape(msg.agent_name)}</b>'
            f'{self_badge}{agent_id_pill} {time_html}'
            f'</div>'
            f'<div style="color: {text_color}; font-size: {self.chat_font_size}px; line-height: 1.6;">{formatted_body}</div>'
            f'</div>'
        )

    def append_message_html(self, msg: ChatMessage):
        block = self.render_message_html_block(msg)
        self.browser.append(block)

        if self.chk_auto_scroll.isChecked():
            self.scroll_to_bottom()

    def rerender_all(self):
        self.browser.clear()
        html_blocks = []
        for msg in self.messages:
            if self.matches_filter(msg):
                html_blocks.append(self.render_message_html_block(msg))

        if html_blocks:
            self.browser.setHtml("".join(html_blocks))
        else:
            self.browser.setHtml(
                "<div style='color: #94a3b8; text-align: center; margin-top: 40px; font-size: 15px;'><i>Không có tin nhắn nào phù hợp.</i></div>"
            )

        if self.chk_auto_scroll.isChecked():
            self.scroll_to_bottom()

    def scroll_to_bottom(self):
        cursor = self.browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.browser.setTextCursor(cursor)
        self.browser.ensureCursorVisible()

    # =============================================================
    # Search & Filter
    # =============================================================

    def matches_filter(self, msg: ChatMessage) -> bool:
        if self.filter_agent != "all":
            if msg.agent_name.strip().lower() != self.filter_agent.strip().lower():
                return False

        if self.filter_keyword:
            kw = self.filter_keyword.lower()
            if kw not in msg.content.lower() and kw not in msg.agent_name.lower():
                return False

        return True

    def on_search_changed(self, text: str):
        self.filter_keyword = text.strip()
        self.rerender_all()

    def on_agent_filter_changed(self, index: int):
        data = self.combo_agent_filter.currentData()
        self.filter_agent = data or "all"
        self.rerender_all()

    def update_agent_filter_combo(self, agent_name: str):
        agent_name = agent_name.strip()
        if not agent_name or agent_name.lower() in ("hệ thống", "lỗi", "system"):
            return
        for i in range(self.combo_agent_filter.count()):
            if self.combo_agent_filter.itemData(i) == agent_name:
                return
        self.combo_agent_filter.addItem(agent_name, agent_name)

    # =============================================================
    # Actions
    # =============================================================

    def on_send_clicked(self):
        text = self.input_text.toPlainText().strip()
        if not text:
            return
        self.sig_send_message.emit(text)
        self.input_text.clear()
        self.input_text.setFocus()

    def clear_display(self):
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa màn hình",
            "Bạn có chắc muốn xóa transcript hiển thị trên màn hình hiện tại?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.messages.clear()
            self.seen_keys.clear()
            self.browser.clear()
            self.append_system_notice("Đã làm sạch màn hình transcript.")

    def export_chat(self):
        if not self.messages:
            QMessageBox.information(self, "Thông báo", "Chưa có tin nhắn nào để xuất.")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Xuất Transcript cuộc họp",
            f"agentmeet_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text File (*.txt);;JSON File (*.json)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith(".json") or "JSON" in selected_filter:
                export_data = [
                    {
                        "message_id": m.message_id,
                        "agent_id": m.agent_id,
                        "agent_name": m.agent_name,
                        "content": m.content,
                        "timestamp": m.timestamp,
                        "read_by": m.read_by,
                    }
                    for m in self.messages
                    if not m.is_system and not m.is_error
                ]
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                lines = []
                for m in self.messages:
                    ts = f"[{m.display_time()}] " if m.display_time() else ""
                    lines.append(f"{ts}{m.agent_name}: {m.content}")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

            QMessageBox.information(self, "Thành công", f"Đã xuất {len(self.messages)} tin nhắn thành công:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất file", f"Không thể lưu file: {e}")
