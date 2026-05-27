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
        self._user_paused = False
        self._pause_until: float = 0.0
        self._last_refresh: Optional[float] = None
        self._total_refreshes = 0
        self._on_cards_update: Optional[Callable] = None
        self._on_scrape_count: Optional[Callable] = None
        self._on_verified_match: Optional[Callable] = None

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
        on_verified_match: Optional[Callable] = None,
    ):
        """Set callbacks for emitting events to the backend."""
        self._on_cards_update = on_cards_update
        self._on_scrape_count = on_scrape_count
        self._on_verified_match = on_verified_match

    def pause(self, duration_seconds: float):
        """Pause refreshing for a given duration (e.g. during a pending match)."""
        self._pause_until = time.time() + duration_seconds
        logger.info("Refresher paused for %.1f seconds", duration_seconds)

    def resume(self):
        """Resume refreshing immediately."""
        self._pause_until = 0.0
        logger.info("Refresher resumed")

    def pause_user(self):
        """Pause refreshing indefinitely (user-initiated)."""
        self._user_paused = True
        logger.info("Refresher paused by user")

    def resume_user(self):
        """Resume refreshing (user-initiated)."""
        self._user_paused = False
        logger.info("Refresher resumed by user")

    @property
    def is_user_paused(self) -> bool:
        """Return whether the refresher is paused by user."""
        return self._user_paused

    async def refresh_once(self) -> Optional[str]:
        """Perform a single refresh cycle. Returns the bot message text or None."""
        if self._user_paused:
            return None
        if time.time() < self._pause_until:
            return None

        try:
            bot = await self.bot_client.get_bot_entity()
            text = await self.bot_client.send_refresh(bot)
            if text is None:
                # Not on listings screen — try to recover
                logger.warning("Refresh returned None — checking if re-navigation is needed")
                on_listings = await self.bot_client.is_on_listings_screen(bot)
                if not on_listings:
                    logger.warning("Bot is NOT on listings screen — re-navigating...")
                    nav_ok = await self.bot_client.navigate_to_listings(bot)
                    if nav_ok:
                        logger.info("Re-navigation successful — retrying refresh")
                        text = await self.bot_client.send_refresh(bot)
                    else:
                        logger.error("Re-navigation failed — scraper may need manual intervention")
                # Still increment counters so we can track attempts
                self._last_refresh = time.time()
                self._total_refreshes += 1
                return text
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

    async def emit_verified_match(self, card_data: dict):
        """Emit a verified unregistered match to the backend."""
        if self._on_verified_match:
            try:
                await self._on_verified_match(card_data)
            except Exception as e:
                logger.error("Failed to emit verified match: %s", e)

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
