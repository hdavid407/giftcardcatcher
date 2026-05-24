import asyncio
import logging
from typing import Optional

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from .config import ScraperConfig

logger = logging.getLogger(__name__)


class BotClient:
    """Manages the Telethon client session — login, reconnect, and bot access."""

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._client: Optional[TelegramClient] = None

    async def start(self) -> TelegramClient:
        """Start and authenticate the Telethon client. Returns the connected client."""
        self._client = TelegramClient(
            session="telegram_scraper",
            api_id=self.config.api_id,
            api_hash=self.config.api_hash,
        )

        await self._client.start(phone=self.config.phone)

        logger.info("Telegram client started and authenticated")
        return self._client

    async def stop(self):
        """Disconnect the client gracefully."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            logger.info("Telegram client disconnected")

    async def get_bot_entity(self):
        """Resolve the target bot username to an entity."""
        return await self._client.get_entity(self.config.target_bot)

    async def get_latest_message(self, bot_entity):
        """Get the most recent message from the bot."""
        async for msg in self._client.iter_messages(bot_entity, limit=1):
            return msg
        return None

    async def click_button_by_text(self, bot_entity, button_text: str, wait: float = 1.5) -> Optional[str]:
        """Find and click a button by its text, then return the updated message text.

        Uses word-boundary matching to avoid false positives (e.g. "Listing"
        matching "Cents Listings").
        """
        import re

        msg = await self.get_latest_message(bot_entity)
        if not msg or not msg.buttons:
            return None

        # Build a regex that matches the text as a whole word/phrase
        pattern = re.compile(r"\b" + re.escape(button_text.lower()) + r"\b")

        for row in msg.buttons:
            for btn in row:
                if pattern.search(btn.text.lower()):
                    await btn.click()
                    logger.info("Clicked button: '%s'", btn.text)
                    await asyncio.sleep(wait)
                    updated = await self.get_latest_message(bot_entity)
                    return updated.text if updated else None

        logger.warning("Button '%s' not found", button_text)
        return None

    async def navigate_to_listings(self, bot_entity) -> bool:
        """
        Navigate to the Listings view with GiftCardMall filter applied.
        Returns True if navigation succeeded.
        """
        logger.info("Navigating to Listings with GiftCardMall filter...")

        # Step 1: Click Main Menu (or send /start)
        result = await self.click_button_by_text(bot_entity, self.config.menu_button_text, wait=2.0)
        if result is None:
            # Try sending /start as fallback
            await self._client.send_message(bot_entity, "/start")
            await asyncio.sleep(2.0)

        # Step 2: Click Listings
        result = await self.click_button_by_text(bot_entity, self.config.listings_button_text, wait=2.0)
        if result is None:
            logger.error("Could not find Listings button")
            return False

        # Step 3: Click Filters
        result = await self.click_button_by_text(bot_entity, self.config.filters_button_text, wait=2.0)
        if result is None:
            logger.error("Could not find Filters button")
            return False

        # Step 4: Select GiftCardMall filter
        result = await self.click_button_by_text(
            bot_entity, self.config.giftcardmall_filter_text, wait=2.0
        )
        if result is None:
            logger.error("Could not find GiftCardMall filter")
            return False

        # Step 5: Go back to listings view (filter is now applied)
        result = await self.click_button_by_text(
            bot_entity, "Back to Listings", wait=2.0
        )
        if result is None:
            logger.warning("Could not find Back to Listings button")
            # Try alternative back buttons
            result = await self.click_button_by_text(bot_entity, "Back", wait=2.0)

        logger.info("Successfully navigated to GiftCardMall listings")
        return True

    async def send_refresh(self, bot_entity) -> Optional[str]:
        """Send the Refresh inline button callback and return the updated message text."""
        return await self.click_button_by_text(bot_entity, self.config.refresh_button_text, wait=1.5)

    async def click_purchase(self, bot_entity, row_index: int) -> bool:
        """Click the Purchase button at the given row index."""
        msg = await self.get_latest_message(bot_entity)
        if not msg or not msg.buttons:
            return False

        if len(msg.buttons) > row_index:
            row = msg.buttons[row_index]
            for btn in row:
                if self.config.purchase_button_text.lower() in btn.text.lower():
                    await btn.click()
                    logger.info("Clicked Purchase button at row %d", row_index)
                    return True

        logger.warning("Could not find Purchase button at row %d", row_index)
        return False

    async def check_registration(self, bot_entity, row_index: int) -> Optional[bool]:
        """
        Click Purchase on a card and check if it's unregistered.
        Returns True if unregistered, False if registered, None if unknown.
        """
        success = await self.click_purchase(bot_entity, row_index)
        if not success:
            return None

        # Wait for the detail view to load
        await asyncio.sleep(2.0)

        msg = await self.get_latest_message(bot_entity)
        if not msg or not msg.text:
            return None

        text = msg.text.lower()
        logger.info("Purchase detail text: %s", msg.text[:200])

        # Check for registration status keywords
        if "unregistered" in text or "un-register" in text:
            logger.info("Card is UNREGISTERED")
            return True
        elif "registered" in text:
            logger.info("Card is REGISTERED")
            return False

        # If we can't determine, try to go back and return unknown
        logger.warning("Could not determine registration status from text")
        return None

    async def go_back_to_listings(self, bot_entity) -> bool:
        """Click the Back button to return to the listings view."""
        back_texts = ["Back", "← Back", "⬅️ Back", "Return", "Main Menu"]
        for text in back_texts:
            result = await self.click_button_by_text(bot_entity, text, wait=1.5)
            if result is not None:
                logger.info("Navigated back using button: '%s'", text)
                return True

        # Fallback: send /start
        await self._client.send_message(bot_entity, "/start")
        await asyncio.sleep(2.0)
        logger.info("Sent /start as fallback to return to menu")
        return True
