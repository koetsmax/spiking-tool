"""Animated holographic client name labels (Discord-style scrolling gradient)."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QGradient, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy

NameHoloTier = Literal["default", "gold", "titan"]

# Warm gold spectrum — no near-white stops (avoids white flashes while scrolling).
_GOLD_STOPS: tuple[tuple[float, str], ...] = (
    (0.00, "#8b6914"),
    (0.18, "#c9a227"),
    (0.36, "#e8c547"),
    (0.54, "#ffd700"),
    (0.72, "#d4af37"),
    (0.90, "#b8860b"),
    (1.00, "#8b6914"),
)

# Titan / holographic — lavender, pink, cyan (Discord holo-ish, no white band).
_TITAN_STOPS: tuple[tuple[float, str], ...] = (
    (0.00, "#6b7fd7"),
    (0.20, "#a9b9ff"),
    (0.40, "#e8a0c8"),
    (0.60, "#5ce1e6"),
    (0.80, "#8847ff"),
    (1.00, "#6b7fd7"),
)

_SCROLL_PIXELS_PER_TICK = 0.75
_TIMER_MS = 40
_NAME_HORIZONTAL_PADDING = 12


def holo_tier_for_group_size(group_size: int | None) -> NameHoloTier:
    if group_size is None or group_size <= 3:
        return "default"
    if group_size >= 5:
        return "titan"
    return "gold"


def _apply_stops(gradient: QLinearGradient, stops: tuple[tuple[float, str], ...]) -> None:
    for position, hex_color in stops:
        gradient.setColorAt(position, QColor(hex_color))


class HolographicNameLabel(QLabel):
    """Client instance name with a smooth, continuously scrolling holo gradient."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._tier: NameHoloTier = "default"
        self._scroll_offset = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(_TIMER_MS)
        self._timer.timeout.connect(self._tick_scroll)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self._apply_text_width_hint()

    def _text_pixel_width(self) -> int:
        text = self.text()
        if not text:
            return 0
        return QFontMetrics(self.font()).horizontalAdvance(text)

    def _apply_text_width_hint(self) -> None:
        width = self._text_pixel_width() + _NAME_HORIZONTAL_PADDING
        self.setMinimumWidth(width)

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self._apply_text_width_hint()

    def sizeHint(self) -> QSize:  # noqa: N802
        base = super().sizeHint()
        width = max(base.width(), self._text_pixel_width() + _NAME_HORIZONTAL_PADDING)
        return QSize(width, base.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def set_holo_tier(self, tier: NameHoloTier) -> None:
        if self._tier == tier:
            return
        self._tier = tier
        if tier == "default":
            self._timer.stop()
            self._scroll_offset = 0.0
            super().setStyleSheet("color: #cdd6f4; background: transparent;")
        else:
            super().setStyleSheet("color: transparent; background: transparent;")
            if not self._timer.isActive():
                self._timer.start()
        self.update()

    def _tick_scroll(self) -> None:
        self._scroll_offset += _SCROLL_PIXELS_PER_TICK
        self.update()

    def _gradient_stops(self) -> tuple[tuple[float, str], ...]:
        return _TITAN_STOPS if self._tier == "titan" else _GOLD_STOPS

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._tier == "default":
            super().paintEvent(event)
            return

        del event
        text = self.text()
        if not text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font = self.font()
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)
        period = max(text_width * 1.8, 72.0)
        offset = self._scroll_offset % period

        x = 0
        y = (self.height() + metrics.ascent() - metrics.descent()) // 2

        grad = QLinearGradient(offset, 0.0, offset + period, 0.0)
        grad.setSpread(QGradient.Spread.RepeatSpread)
        _apply_stops(grad, self._gradient_stops())

        painter.setFont(font)
        painter.setPen(QPen(grad, 0))
        painter.drawText(x, y, text)
