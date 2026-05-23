from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from controller_ui.client_log_store import ClientLogStore


class LoggingTab(QWidget):
    def __init__(self, log_store: "ClientLogStore") -> None:
        super().__init__()
        self._log_store = log_store
        self._selected_client: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Client logs")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        self.client_list = QListWidget()
        self.client_list.setObjectName("logClientList")
        self.client_list.setMinimumWidth(120)
        self.client_list.setMaximumWidth(200)
        self.client_list.currentTextChanged.connect(self._on_client_selected)
        splitter.addWidget(self.client_list)

        log_panel = QFrame()
        log_panel.setObjectName("logViewerPanel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(8, 8, 8, 8)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("logViewer")
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_view.setPlaceholderText("Select a client to view logs")
        log_layout.addWidget(self.log_view)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([140, 700])

    def sync_client_list(self, client_names: list[str]) -> None:
        current = self.client_list.currentItem()
        current_name = current.text() if current else self._selected_client
        self.client_list.blockSignals(True)
        self.client_list.clear()
        for name in client_names:
            if name == "Controller":
                continue
            self.client_list.addItem(QListWidgetItem(name))
        self.client_list.blockSignals(False)

        if not client_names:
            self._selected_client = None
            self.log_view.clear()
            return

        names = [self.client_list.item(i).text() for i in range(self.client_list.count())]
        if not names:
            return

        pick = current_name if current_name in names else names[0]
        items = self.client_list.findItems(pick, Qt.MatchFlag.MatchExactly)
        if items:
            self.client_list.setCurrentItem(items[0])
        else:
            self.client_list.setCurrentRow(0)
        self._show_logs_for(self.client_list.currentItem().text())

    def append_log(self, client_name: str, message: str) -> None:
        if client_name == self._selected_client:
            self.log_view.append(message)
            scrollbar = self.log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _on_client_selected(self, client_name: str) -> None:
        if client_name:
            self._show_logs_for(client_name)

    def _show_logs_for(self, client_name: str) -> None:
        self._selected_client = client_name
        self.log_view.setPlainText("\n".join(self._log_store.get_lines(client_name)))
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
