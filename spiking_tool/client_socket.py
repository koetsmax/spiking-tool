"""Resilient Socket.IO emit helpers for game clients."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import socketio

    from spiking_tool.client_session import ClientSessionState

logger = logging.getLogger(__name__)


async def safe_emit(sio: "socketio.AsyncClient", event: str, data: Any = None) -> bool:
    if not getattr(sio, "connected", False):
        return False
    try:
        await sio.emit(event, data=data)
        return True
    except Exception:
        logger.debug("Emit %s failed (server offline)", event, exc_info=True)
        return False
