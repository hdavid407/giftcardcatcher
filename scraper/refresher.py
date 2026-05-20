import asyncio
import logging
import time
from typing import Optional

from .bot_client import BotClient
from .config import ScraperConfig

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

    @property
    def last_refresh(self) -> Optional[float]:
        return self._last_refresh

    @property
    def total_refreshes(self) -> int:
        return self._total_refreshes

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
