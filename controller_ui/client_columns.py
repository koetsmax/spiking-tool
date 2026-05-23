"""Expandable client-table column definitions for the controller."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

if TYPE_CHECKING:
    from controller_ui.client_manager import Client
    from controller_ui.main_window import ControllerWindow

MetricState = Literal["unknown", "ok", "bad"]

_METRIC_COLORS = {
    "ok": "#a6e3a1",
    "bad": "#f38ba8",
    "unknown": "#585b70",
}

_METRIC_TOOLTIPS = {
    "resolution": {
        "ok": "Game resolution is 800×600",
        "bad": "Game resolution is not 800×600",
        "unknown": "Resolution unknown (game window not found)",
    },
}


class MetricIndicator(QWidget):
    """Small colored square for ok / bad / unknown metric state."""

    def __init__(self, metric_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._metric_id = metric_id
        self._state: MetricState = "unknown"
        self.setFixedSize(18, 18)
        self.setToolTip(_METRIC_TOOLTIPS.get(metric_id, {}).get("unknown", ""))

    def set_state(self, state: MetricState) -> None:
        if self._state == state:
            return
        self._state = state
        tips = _METRIC_TOOLTIPS.get(self._metric_id, {})
        self.setToolTip(tips.get(state, state))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter

        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(_METRIC_COLORS[self._state]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)


class ClientColumnSpec(ABC):
    """One column in the clients table; subclass to add new columns."""

    def __init__(self, column_id: str, header: str) -> None:
        self.column_id = column_id
        self.header = header

    @abstractmethod
    def resize_mode(self) -> QHeaderView.ResizeMode:
        ...

    def fixed_width(self) -> Optional[int]:
        return None

    @abstractmethod
    def populate(
        self,
        table: QTableWidget,
        row: int,
        column_index: int,
        client: "Client",
        window: "ControllerWindow",
    ) -> None:
        ...

    def refresh(self, client: "Client") -> None:
        """Update cell widgets from ``client.metrics`` (metric columns only)."""


class ActiveColumn(ClientColumnSpec):
    def __init__(self) -> None:
        super().__init__("active", "Active")

    def resize_mode(self) -> QHeaderView.ResizeMode:
        return QHeaderView.ResizeMode.Fixed

    def fixed_width(self) -> Optional[int]:
        return 56

    def populate(self, table, row, column_index, client, window) -> None:
        was_checked = client.active_checkbox.isChecked() if client.active_checkbox else True
        checkbox = QCheckBox()
        checkbox.setChecked(was_checked)
        client.active_checkbox = checkbox
        table.setCellWidget(row, column_index, window._centered_cell_widget(checkbox))


class NameColumn(ClientColumnSpec):
    def __init__(self) -> None:
        super().__init__("name", "Instance")

    def resize_mode(self) -> QHeaderView.ResizeMode:
        return QHeaderView.ResizeMode.ResizeToContents

    def populate(self, table, row, column_index, client, window) -> None:
        del window
        item = QTableWidgetItem(client.name)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(row, column_index, item)


class MetricIndicatorColumn(ClientColumnSpec):
    """Colored indicator driven by ``client.metrics[metric_id]``."""

    def __init__(self, metric_id: str, header: str) -> None:
        super().__init__(metric_id, header)
        self.metric_id = metric_id

    def resize_mode(self) -> QHeaderView.ResizeMode:
        return QHeaderView.ResizeMode.Fixed

    def fixed_width(self) -> Optional[int]:
        return 44

    def populate(self, table, row, column_index, client, window) -> None:
        del window
        indicator = MetricIndicator(self.metric_id)
        indicator.set_state(client.metrics.get(self.metric_id, "unknown"))
        client.column_widgets[self.column_id] = indicator
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addStretch()
        layout.addWidget(indicator, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        table.setCellWidget(row, column_index, container)

    def refresh(self, client: "Client") -> None:
        indicator = client.column_widgets.get(self.column_id)
        if isinstance(indicator, MetricIndicator):
            indicator.set_state(client.metrics.get(self.metric_id, "unknown"))


class ShipColumn(ClientColumnSpec):
    def __init__(self) -> None:
        super().__init__("ship", "Ship")

    def resize_mode(self) -> QHeaderView.ResizeMode:
        return QHeaderView.ResizeMode.Stretch

    def populate(self, table, row, column_index, client, window) -> None:
        ship_types = ["Sloop", "Brigantine", "Galleon", "Captaincy"]
        ship_type = client.ship_combo.currentText() if client.ship_combo else client.ship_type
        combo = QComboBox()
        combo.addItems(ship_types)
        combo.setCurrentText(ship_type)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        client.ship_combo = combo

        def ship_type_changed(text, c=client):
            c.ship_type = text
            window.sio.emit(
                "change_ship",
                data={"client": c.name, "ship_type": text},
            )

        combo.currentTextChanged.connect(ship_type_changed)
        table.setCellWidget(row, column_index, combo)


class ClickableStatusLabel(QLabel):
    """Status cell label; copies match details to the clipboard when a match is set."""

    def __init__(self, client: "Client") -> None:
        super().__init__()
        self._client = client

    def update_match_style(self) -> None:
        if self._client.match is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Click to copy match details")
            self.setStyleSheet("color: #89b4fa; text-decoration: underline;")
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("")
            self.setStyleSheet("")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._client.match is not None
        ):
            QApplication.clipboard().setText(self._client.match.to_clipboard_text())
        super().mousePressEvent(event)


class StatusColumn(ClientColumnSpec):
    def __init__(self) -> None:
        super().__init__("status", "Status")

    def resize_mode(self) -> QHeaderView.ResizeMode:
        return QHeaderView.ResizeMode.Stretch

    def populate(self, table, row, column_index, client, window) -> None:
        del window
        label = ClickableStatusLabel(client)
        label.setText(client.status)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.update_match_style()
        client.status_label = label
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.addWidget(label, 1)
        table.setCellWidget(row, column_index, container)


# Register columns here (order = table column order). Add new MetricIndicatorColumn entries as needed.
CLIENT_TABLE_COLUMNS: tuple[ClientColumnSpec, ...] = (
    ActiveColumn(),
    NameColumn(),
    MetricIndicatorColumn("resolution", "Res"),
    ShipColumn(),
    StatusColumn(),
)

_METRIC_COLUMNS: dict[str, MetricIndicatorColumn] = {
    col.metric_id: col
    for col in CLIENT_TABLE_COLUMNS
    if isinstance(col, MetricIndicatorColumn)
}


def configure_client_table(table: QTableWidget) -> None:
    table.setColumnCount(len(CLIENT_TABLE_COLUMNS))
    table.setHorizontalHeaderLabels([col.header for col in CLIENT_TABLE_COLUMNS])
    header = table.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for index, spec in enumerate(CLIENT_TABLE_COLUMNS):
        header.setSectionResizeMode(index, spec.resize_mode())
        width = spec.fixed_width()
        if width is not None:
            table.setColumnWidth(index, width)
    table.verticalHeader().setDefaultSectionSize(40)


def populate_client_row(
    table: QTableWidget,
    row: int,
    client: "Client",
    window: "ControllerWindow",
) -> None:
    for column_index, spec in enumerate(CLIENT_TABLE_COLUMNS):
        spec.populate(table, row, column_index, client, window)


def refresh_client_metrics(client: "Client") -> None:
    for spec in _METRIC_COLUMNS.values():
        spec.refresh(client)
