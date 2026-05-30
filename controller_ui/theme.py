from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #45475a;
    border-radius: 6px;
    background-color: #181825;
}
QTabBar::tab {
    background-color: #313244;
    color: #a6adc8;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #45475a;
    color: #cdd6f4;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 600;
}
QPushButton:hover:enabled { background-color: #b4befe; }
QPushButton:pressed:enabled { background-color: #74c7ec; }
QPushButton:disabled {
    background-color: #2a3148;
    color: #7f849c;
    border: 1px solid #45475a;
}
QPushButton#autoHoldToggleButton[autoHoldActive="false"] {
    background-color: #6c7086;
    color: #1e1e2e;
    border: none;
}
QPushButton#autoHoldToggleButton[autoHoldActive="false"]:hover:enabled {
    background-color: #7f849c;
}
QPushButton#autoHoldToggleButton[autoHoldActive="true"] {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border: 2px solid #94e2d5;
}
QPushButton#autoHoldToggleButton[autoHoldActive="true"]:hover:enabled {
    background-color: #b8f0c0;
}
QPushButton#entryConfirmButton {
    background-color: #a6e3a1;
    color: #1e1e2e;
    padding: 4px;
    min-width: 36px;
    max-width: 36px;
    font-size: 16px;
    font-weight: 700;
}
QPushButton#entryConfirmButton:hover:enabled { background-color: #b8f0c0; }
QPushButton#entryConfirmButton:pressed:enabled { background-color: #94e2d5; }
QPushButton#entryConfirmButton:disabled {
    background-color: #2a3148;
    color: #7f849c;
    border: 1px solid #45475a;
}
QPushButton#clientKillButton {
    background-color: #f38ba8;
    color: #1e1e2e;
    padding: 4px 8px;
    font-size: 12px;
}
QPushButton#clientKillButton:hover:enabled { background-color: #f5a8b8; }
QPushButton#clientKillButton:pressed:enabled { background-color: #e06c75; }
QPushButton#clientAfkOnButton {
    background-color: #a6e3a1;
    color: #1e1e2e;
    padding: 4px 8px;
    font-size: 12px;
}
QPushButton#clientAfkOnButton:hover:enabled { background-color: #b8f0c0; }
QPushButton#clientAfkOnButton:pressed:enabled { background-color: #94e2d5; }
QPushButton[lastPressed="true"] {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border: 2px solid #94e2d5;
}
QPushButton[lastPressed="true"]:hover { background-color: #b8f0c0; }
QComboBox, QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 8px;
}
QComboBox::drop-down { border: none; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #585b70;
    background-color: #313244;
}
QCheckBox::indicator:checked {
    background-color: #a6e3a1;
    border-color: #a6e3a1;
}
QCheckBox:disabled {
    color: #7f849c;
}
QCheckBox::indicator:disabled {
    background-color: #2a3148;
    border-color: #45475a;
}
QLineEdit:disabled {
    background-color: #2a3148;
    color: #7f849c;
    border-color: #45475a;
}
QScrollArea {
    border: 1px solid #45475a;
    border-radius: 6px;
    background-color: #181825;
}
QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #89b4fa;
}
QLabel#biggestMatch {
    background-color: #313244;
    border-radius: 6px;
    padding: 8px;
}
QFrame#clientsPanel {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 8px;
}
QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    gridline-color: #313244;
}
QTableWidget::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    padding: 8px;
    border: none;
    font-weight: 600;
}
QListWidget#logClientList {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 6px;
}
QListWidget#logClientList::item {
    padding: 8px;
}
QListWidget#logClientList::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}
QFrame#logViewerPanel {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 8px;
}
QTextEdit#logViewer {
    background-color: #11111b;
    color: #cdd6f4;
    border: none;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))
