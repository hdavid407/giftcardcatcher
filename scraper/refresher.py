import asyncio
import logging
import time
from typing import Optional, Callable

from .bot_client import BotClient
from .config import ScraperConfig
from .matcher import CardInfo

logger = logging.getLogger(__name__)


class Refresher:
    """Manages the polling loop: refresh → parse → match → notify."""

    def __init__(self, bot_client: BotClient, config: ScraperConfig):
        self.bot_client = bot_client
        self.config = config
        self._running = False
        self._pause_until: float = 0.0
        self._last_refresh: Optional[float] = None
        self._total_refreshes = 0
        self._on_cards_update: Optional[Callable] = None
        self._on_scrape_count: Optional[Callable] = None

    @property
    def last_refresh(self) -> Optional[float]:
        return self._last_refresh

    @property
    def total_refreshes(self) -> int:
        return self._total_refreshes

    def set_callbacks(
        self,
        on_cards_update: Optional[Callable] = None,
        on_scrape_count: Optional[Callable] = None,
    ):
        """Set callbacks for emitting events to the backend."""
        self._on_cards_update = on_cards_update
        self._on_scrape_count = on_scrape_count

    def pause(self, duration_seconds: float):
        """Pause refreshing for a given duration (e.g. during a pending match)."""
        self._pause_until = time.time() + duration_seconds
        logger.info("Refresher paused for %.1f seconds", duration_seconds)

    def resume(self):
        """Resume refreshing immediately."""
        self._pause_until = 0.0
        logger.info("Refresher resumed")

    async def refresh_once(self) -> Optional[str]:
        """Perform a single refresh cycle. Returns the bot message text or None."""
        if time.time() < self._pause_until:
            return None

        try:
            bot = await self.bot_client.get_bot_entity()
            text = await self.bot_client.send_refresh(bot)
            self._last_refresh = time.time()
            self._total_refreshes += 1
            return text
        except Exception as e:
            logger.error("Refresh failed: %s", e)
            return None

    async def emit_scrape_metrics(self, cards: list[CardInfo]):
        """Emit scrape count and cards update to backend."""
        if self._on_scrape_count:
            try:
                await self._on_scrape_count(self._total_refreshes)
            except Exception as e:
                logger.error("Failed to emit scrape count: %s", e)

        if self._on_cards_update and cards:
            try:
                cards_data = [
                    {
                        "card_number": c.card_number,
                        "bin": c.bin,
                        "amount": c.amount,
                        "currency": c.currency,
                        "discount": c.discount,
                        "button_row": c.button_row,
                        "is_match": c.is_match,
                        "raw_text": c.raw_text,
                    }
                    for c in cards
                ]
                await self._on_cards_update(cards_data)
            except Exception as e:
                logger.error("Failed to emit cards update: %s", e)

    async def poll_loop(self, on_text: callable):
        """Continuously poll the bot, calling on_text with each message."""
        self._running = True
        logger.info(
            "Starting poll loop (interval=%ds)",
            self.config.poll_interval,
        )

        while self._running:
            text = await self.refresh_once()
            if text is not None:
                await on_text(text)
            await asyncio.sleep(self.config.poll_interval)

        logger.info("Poll loop stopped")

    def stop(self):
        """Signal the poll loop to stop."""
        self._running = False
