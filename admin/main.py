"""Main entry point for AgentMeet Admin Console PyQt5 application with Light Theme default and large fonts."""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from agentmeet.ui.main_window import MainWindow
from agentmeet.ui.theme import LIGHT_THEME_QSS


def main():
    # Enable High DPI scaling for crisp display
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("AgentMeet Admin Console")
    app.setOrganizationName("AgentMeet")

    # Cỡ chữ to hơn, sắc nét, dễ đọc (11pt Segoe UI)
    font = QFont("Segoe UI", 11)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    # Áp dụng Light Theme mặc định
    app.setStyleSheet(LIGHT_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
