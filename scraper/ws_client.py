import asyncio
import logging
import time
from typing import Optional, Callable

import socketio

from .config import ScraperConfig
from .matcher import GiftCardMatch

logger = logging.getLogger(__name__)


class ScraperWSClient:
    """
    Socket.IO client connecting the scraper to the Flask backend.

    Emits: match_found (when a target card is detected)
    Listens for: purchase_approved, purchase_denied
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._sio = socketio.AsyncClient()
        self._connected = False
        self._approval_event = asyncio.Event()
        self._denial_event = asyncio.Event()
        self._approved = False

        self._register_handlers()

    def _register_handlers(self):
        @self._sio.on("connect")
        def on_connect():
            self._connected = True
            logger.info("Connected to backend at %s", self.config.backend_url)

        @self._sio.on("disconnect")
        def on_disconnect():
            self._connected = False
            logger.warning("Disconnected from backend")
            # Auto-reconnect is handled by Socket.IO library

        @self._sio.on("purchase_approved")
        def on_purchase_approved(data=None):
            logger.info("Received purchase approval from backend")
            self._approved = True
            self._approval_event.set()

        @self._sio.on("purchase_denied")
        def on_purchase_denied(data=None):
            logger.info("Received purchase denial from backend")
            self._approved = False
            self._denial_event.set()

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

    async def emit_match(self, match: GiftCardMatch):
        """Emit a match_found event to the backend."""
        data = {
            "row_index": match.row_index,
            "card_text": match.card_text,
            "price": match.price,
        }
        await self._sio.emit("match_found", data)
        logger.info("Emitted match_found: %s", data)

    async def wait_for_approval(self, timeout: float) -> Optional[bool]:
        """
        Wait for the user to approve or deny the purchase.
        Returns True if approved, False if denied, None if timeout.
        """
        self._approval_event.clear()
        self._denial_event.clear()
        self._approved = False

        try:
            # Wait for either approval, denial, or timeout
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(self._wait_event(self._approval_event)),
                    asyncio.create_task(self._wait_event(self._denial_event)),
                    asyncio.create_task(asyncio.sleep(timeout)),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

            if self._approval_event.is_set():
                return True
            elif self._denial_event.is_set():
                return False
            else:
                logger.info("Match approval timed out after %.1f seconds", timeout)
                return None
        except Exception as e:
            logger.error("Error waiting for approval: %s", e)
            return None

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

    @staticmethod
    async def _wait_event(event: asyncio.Event):
        await event.wait()
