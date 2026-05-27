import asyncio
import logging
import time
from typing import Optional, Callable

import socketio

from .config import ScraperConfig

logger = logging.getLogger(__name__)


class ScraperWSClient:
    """
    Socket.IO client connecting the scraper to the Flask backend.

    Listens for: purchase_card, scraper_control, target_amount_changed
    Emits: status_update, cards_update, scrape_count, scraper_state
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._sio = socketio.AsyncClient()
        self._connected = False
        self._reconnect_handler: Optional[Callable] = None
        self._has_connected_before = False

        self._register_handlers()

    def set_reconnect_handler(self, handler: Callable):
        """Set a callback invoked when the client reconnects to the backend.

        The handler receives no arguments. Use it to re-sync state
        (scrape count, latest cards, scraper status) after a reconnect.
        """
        self._reconnect_handler = handler

    def _register_handlers(self):
        @self._sio.on("connect")
        def on_connect():
            self._connected = True
            logger.info("Connected to backend at %s", self.config.backend_url)
            if self._has_connected_before and self._reconnect_handler:
                try:
                    self._reconnect_handler()
                except Exception as e:
                    logger.error("Reconnect handler failed: %s", e)
            self._has_connected_before = True

        @self._sio.on("disconnect")
        def on_disconnect():
            self._connected = False
            logger.warning("Disconnected from backend")

    async def connect(self):
        """Connect to the Flask backend."""
        headers = {"X-API-Key": self.config.api_key} if self.config.api_key else {}
        await self._sio.connect(
            self.config.backend_url,
            headers=headers,
            transports=["websocket", "polling"],
        )

    async def disconnect(self):
        """Disconnect from the backend."""
        if self._connected:
            await self._sio.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_purchase_handler(self, handler: Callable[[int], None]):
        """Set a callback for purchase_card events from the backend.

        handler(row_index: int) — called when the user clicks Buy on a card.
        """

        @self._sio.on("purchase_card")
        def on_purchase_card(data: dict):
            row_index = data.get("row_index")
            if row_index is None:
                logger.warning("purchase_card received without row_index")
                return
            logger.info("Received purchase_card for row %d", row_index)
            handler(row_index)

    def set_control_handler(self, handler: Callable[[str], None]):
        """Set a callback for scraper_control events from the backend.

        handler(action: str) where action is "pause", "resume", or "restart".
        """

        @self._sio.on("scraper_control")
        def on_scraper_control(data: dict):
            action = data.get("action", "")
            logger.info("Received scraper_control: %s", action)
            handler(action)

    async def emit_scraper_state(self, state: dict):
        """Emit the current scraper state to the backend."""
        await self._sio.emit("scraper_state", state)
        logger.info("Emitted scraper_state: %s", state)

    async def emit_status(self, status: dict):
        """Emit a status update to the backend."""
        await self._sio.emit("status_update", status)

    async def emit_cards_update(self, cards: list[dict]):
        """Emit the full card list from the latest refresh."""
        await self._sio.emit("cards_update", {"cards": cards, "timestamp": time.time()})

    async def emit_scrape_count(self, count: int):
        """Emit the total scrape count."""
        await self._sio.emit("scrape_count", {"count": count})

    def set_target_amount_handler(self, handler: Callable[[float], None]):
        """Set a callback for when the target amount changes."""

        @self._sio.on("target_amount_changed")
        def on_target_amount_changed(data: dict):
            amount = data.get("amount", 50.0)
            logger.info("Received target amount change: %.2f", amount)
            handler(amount)
