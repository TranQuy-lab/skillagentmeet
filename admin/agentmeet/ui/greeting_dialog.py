"""Dialog for customizing and sending greeting message after connection."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from agentmeet.config import GREETING_TEMPLATES


class GreetingDialog(QDialog):
    """Hộp thoại cho phép người dùng chọn mẫu hoặc tự soạn lời chào trước khi gửi vào phòng."""

    sig_send_greeting = pyqtSignal(str)

    def __init__(self, parent=None, current_agent_name="Admin"):
        super().__init__(parent)
        self.current_agent_name = current_agent_name
        self.setWindowTitle("👋 Gửi lời chào vào phòng")
        self.resize(520, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header info
        info_label = QLabel(
            "<b>Chọn mẫu lời chào hoặc chỉnh sửa nội dung bên dưới trước khi gửi:</b>"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Template Selector
        tpl_layout = QHBoxLayout()
        tpl_layout.addWidget(QLabel("Mẫu có sẵn:"))
        self.combo_tpl = QComboBox()
        for tpl in GREETING_TEMPLATES:
            self.combo_tpl.addItem(tpl["title"], tpl["content"])
        self.combo_tpl.addItem("— Tự soạn tin nhắn mới —", "")
        self.combo_tpl.currentIndexChanged.connect(self.on_template_selected)
        tpl_layout.addWidget(self.combo_tpl, stretch=1)
        layout.addLayout(tpl_layout)

        # Content editor
        self.txt_content = QTextEdit()
        self.txt_content.setPlaceholderText("Nhập nội dung lời chào...")
        layout.addWidget(self.txt_content)

        # Populate initial template
        self.on_template_selected(0)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Hủy bỏ")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_send = QPushButton("🚀 Gửi lời chào ngay")
        self.btn_send.setObjectName("btnGreeting")
        self.btn_send.clicked.connect(self.on_send_clicked)
        btn_layout.addWidget(self.btn_send)

        layout.addLayout(btn_layout)

    def on_template_selected(self, index: int):
        template_text = self.combo_tpl.currentData()
        if template_text:
            # Replace placeholder name if needed
            formatted = template_text.replace("Admin", self.current_agent_name)
            self.txt_content.setPlainText(formatted)
        elif index == len(GREETING_TEMPLATES):  # Custom
            self.txt_content.clear()
            self.txt_content.setFocus()

    def on_send_clicked(self):
        text = self.txt_content.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Chưa nhập nội dung", "Vui lòng nhập nội dung lời chào trước khi gửi.")
            return

        self.sig_send_greeting.emit(text)
        self.accept()
