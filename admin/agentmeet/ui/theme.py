"""Themes and visual styles for PyQt5 AgentMeet Console.
Supports both modern Light Theme (default) and Dark Theme with large, crisp typography.
"""

import hashlib

# =====================================================================
# LIGHT THEME (Giao diện sáng thanh lịch, độ tương phản cao, chữ to rõ)
# =====================================================================
LIGHT_THEME_QSS = """
/* Global Window & Font */
QMainWindow, QDialog, QWidget {
    background-color: #f1f5f9;
    color: #0f172a;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 14px;
}

/* ToolBar & Menu */
QMenuBar {
    background-color: #ffffff;
    color: #1e293b;
    border-bottom: 1px solid #e2e8f0;
    padding: 3px 6px;
    font-size: 14px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #e2e8f0;
}
QMenu {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
    font-size: 14px;
}
QMenu::item {
    padding: 7px 26px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}

/* ToolBar */
QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    spacing: 8px;
    padding: 6px 10px;
    font-size: 14px;
}

/* GroupBox / Panels */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 20px;
    font-weight: bold;
    padding-top: 16px;
    font-size: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #475569;
    font-size: 13px;
}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 14px;
    selection-background-color: #93c5fd;
    selection-color: #0f172a;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #3b82f6;
    background-color: #ffffff;
}

/* Buttons */
QPushButton {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background-color: #e2e8f0;
}
QPushButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Special Button Variants */
QPushButton#btnConnect {
    background-color: #16a34a;
    color: #ffffff;
    border: 1px solid #15803d;
    font-weight: bold;
}
QPushButton#btnConnect:hover {
    background-color: #15803d;
}

QPushButton#btnLeave {
    background-color: #dc2626;
    color: #ffffff;
    border: 1px solid #b91c1c;
    font-weight: bold;
}
QPushButton#btnLeave:hover {
    background-color: #b91c1c;
}

QPushButton#btnGreeting {
    background-color: #0284c7;
    color: #ffffff;
    border: 1px solid #0369a1;
    font-weight: bold;
}
QPushButton#btnGreeting:hover {
    background-color: #0369a1;
}

QPushButton#btnSend {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    font-size: 14px;
    font-weight: bold;
}
QPushButton#btnSend:hover {
    background-color: #1d4ed8;
}

/* Status Bar */
QStatusBar {
    background-color: #ffffff;
    color: #475569;
    border-top: 1px solid #e2e8f0;
    font-size: 13px;
    padding: 3px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #f1f5f9;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 25px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Splitter */
QSplitter::handle {
    background-color: #cbd5e1;
}
QSplitter::handle:hover {
    background-color: #3b82f6;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background-color: #ffffff;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #e2e8f0;
    color: #475569;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0284c7;
    font-weight: bold;
    border-top: 3px solid #0284c7;
}

/* ProgressBar */
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    text-align: center;
    background-color: #f1f5f9;
    color: #0f172a;
    font-size: 12px;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}

/* Lists and Tables */
QListWidget, QTableWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
    color: #0f172a;
    font-size: 13px;
}
QListWidget::item {
    padding: 7px 10px;
    border-radius: 5px;
    margin-bottom: 3px;
    border-bottom: 1px solid #f1f5f9;
}
QListWidget::item:hover {
    background-color: #f1f5f9;
}
QListWidget::item:selected {
    background-color: #e0f2fe;
    color: #0369a1;
}
"""

# =====================================================================
# DARK THEME (Giao diện tối, hỗ trợ chuyển đổi nếu muốn)
# =====================================================================
DARK_THEME_QSS = """
QMainWindow, QDialog, QWidget {
    background-color: #12131a;
    color: #e2e8f0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 14px;
}
QMenuBar {
    background-color: #1a1b26;
    color: #cbd5e1;
    border-bottom: 1px solid #282a36;
    padding: 3px 6px;
    font-size: 14px;
}
QMenuBar::item:selected {
    background-color: #2e303e;
    border-radius: 4px;
}
QMenu {
    background-color: #1a1b26;
    color: #e2e8f0;
    border: 1px solid #32364c;
    border-radius: 6px;
    padding: 4px;
    font-size: 14px;
}
QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}
QToolBar {
    background-color: #161722;
    border-bottom: 1px solid #232534;
    spacing: 8px;
    padding: 6px 10px;
    font-size: 14px;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1e202e;
    color: #f8fafc;
    border: 1px solid #33364f;
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 14px;
    selection-background-color: #3b82f6;
}
QPushButton {
    background-color: #282a3c;
    color: #f1f5f9;
    border: 1px solid #3c4059;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #363952;
}
QPushButton#btnConnect { background-color: #15803d; color: #ffffff; }
QPushButton#btnLeave { background-color: #991b1b; color: #ffffff; }
QPushButton#btnGreeting { background-color: #0369a1; color: #ffffff; }
QPushButton#btnSend { background-color: #2563eb; color: #ffffff; }
QStatusBar {
    background-color: #14151e;
    color: #94a3b8;
    border-top: 1px solid #232535;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #282a3d;
    background-color: #161722;
}
QTabBar::tab {
    background-color: #1b1d2a;
    color: #94a3b8;
    padding: 8px 16px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #161722;
    color: #38bdf8;
    font-weight: bold;
    border-top: 3px solid #38bdf8;
}
QListWidget {
    background-color: #161723;
    border: 1px solid #26283b;
    color: #e2e8f0;
    font-size: 13px;
}
QListWidget::item:hover { background-color: #222436; }
QListWidget::item:selected { background-color: #2a314e; color: #60a5fa; }
"""

# Bảng màu đại diện cho các agent trong Light Theme (màu đậm đà, nền thẻ trắng trang nhã)
LIGHT_AGENT_PALETTES = [
    {"name": "#0284c7", "bg": "#ffffff", "border": "#0284c7", "badge_bg": "#e0f2fe", "badge_color": "#0369a1"},  # Sky Blue
    {"name": "#7c3aed", "bg": "#ffffff", "border": "#7c3aed", "badge_bg": "#ede9fe", "badge_color": "#6d28d9"},  # Purple
    {"name": "#db2777", "bg": "#ffffff", "border": "#db2777", "badge_bg": "#fce7f3", "badge_color": "#be185d"},  # Pink
    {"name": "#059669", "bg": "#ffffff", "border": "#059669", "badge_bg": "#d1fae5", "badge_color": "#047857"},  # Emerald Green
    {"name": "#d97706", "bg": "#ffffff", "border": "#d97706", "badge_bg": "#fef3c7", "badge_color": "#b45309"},  # Amber
    {"name": "#4f46e5", "bg": "#ffffff", "border": "#4f46e5", "badge_bg": "#e0e7ff", "badge_color": "#3730a3"},  # Indigo
    {"name": "#0d9488", "bg": "#ffffff", "border": "#0d9488", "badge_bg": "#ccfbf1", "badge_color": "#0f766e"},  # Teal
    {"name": "#ea580c", "bg": "#ffffff", "border": "#ea580c", "badge_bg": "#ffedd5", "badge_color": "#c2410c"},  # Orange
]

# Bảng màu cho Dark Theme
DARK_AGENT_PALETTES = [
    {"name": "#38bdf8", "bg": "rgba(56, 189, 248, 0.08)", "border": "#0284c7"},
    {"name": "#a855f7", "bg": "rgba(168, 85, 247, 0.08)", "border": "#7e22ce"},
    {"name": "#ec4899", "bg": "rgba(236, 72, 153, 0.08)", "border": "#be185d"},
    {"name": "#10b981", "bg": "rgba(16, 185, 129, 0.08)", "border": "#047857"},
    {"name": "#f59e0b", "bg": "rgba(245, 158, 11, 0.08)", "border": "#b45309"},
    {"name": "#6366f1", "bg": "rgba(99, 102, 241, 0.08)", "border": "#4338ca"},
    {"name": "#14b8a6", "bg": "rgba(20, 184, 166, 0.08)", "border": "#0f766e"},
    {"name": "#f97316", "bg": "rgba(249, 115, 22, 0.08)", "border": "#c2410c"},
]


def get_agent_color_style(agent_name: str, is_self: bool = False, dark_mode: bool = False) -> dict:
    """Tạo màu sắc nhận diện riêng biệt cho từng agent dựa trên hash của tên."""
    if not dark_mode:
        # Light Theme
        if is_self or agent_name.lower() in ("admin", "you"):
            return {
                "name": "#1d4ed8",
                "bg": "#eff6ff",
                "border": "#2563eb",
                "badge_bg": "#2563eb",
                "badge_color": "#ffffff",
                "card_border": "#bfdbfe",
            }

        h = int(hashlib.md5(agent_name.encode("utf-8")).hexdigest(), 16)
        palette = LIGHT_AGENT_PALETTES[h % len(LIGHT_AGENT_PALETTES)]
        return {
            "name": palette["name"],
            "bg": palette["bg"],
            "border": palette["border"],
            "badge_bg": palette["badge_bg"],
            "badge_color": palette["badge_color"],
            "card_border": "#e2e8f0",
        }
    else:
        # Dark Theme
        if is_self or agent_name.lower() in ("admin", "you"):
            return {
                "name": "#60a5fa",
                "bg": "rgba(59, 130, 246, 0.12)",
                "border": "#3b82f6",
                "badge_bg": "#1d4ed8",
                "badge_color": "#ffffff",
                "card_border": "#3b82f6",
            }

        h = int(hashlib.md5(agent_name.encode("utf-8")).hexdigest(), 16)
        palette = DARK_AGENT_PALETTES[h % len(DARK_AGENT_PALETTES)]
        return {
            "name": palette["name"],
            "bg": palette["bg"],
            "border": palette["border"],
            "badge_bg": palette["border"],
            "badge_color": "#ffffff",
            "card_border": palette["border"],
        }
