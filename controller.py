"""Entry point for the spiking-tool controller GUI."""

import logging
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from controller_ui import Controller, apply_dark_theme
from spiking_tool.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    apply_dark_theme(app)

    window = Controller()
    window.show()

    timer = QTimer()
    timer.timeout.connect(window.sio.events.processEvents)
    timer.start(50)

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
