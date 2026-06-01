"""Client diagnostics: local file + controller remote log."""

from __future__ import annotations

import logging

logger = logging.getLogger("spiking_tool.client")


def client_diagnostic_log(message: str, level: str = "INFO") -> None:
    """Write to spiking-tool-client.log; RemoteLogHandler forwards to the controller."""
    text = message.rstrip()
    if not text:
        return
    logger.log(getattr(logging, level, logging.INFO), text)
