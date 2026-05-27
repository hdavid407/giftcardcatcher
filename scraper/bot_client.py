import asyncio
import logging
from typing import Optional

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from .config import ScraperConfig
from .filter_verifier import FilterVerifier

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

    @property
    def is_connected(self) -> bool:
        """Return whether the Telegram client is connected."""
        return self._client is not None and self._client.is_connected()

    async def restart(self) -> bool:
        """Disconnect and reconnect the Telegram client, then re-navigate to listings."""
        try:
            logger.info("Restarting Telegram client...")
            await self.stop()
            await asyncio.sleep(1.0)
            await self.start()
            bot_entity = await self.get_bot_entity()
            nav_ok = await self.navigate_to_listings(bot_entity)
            if not nav_ok:
                logger.error("Restarted but navigation to listings failed")
                return False

            # Also verify the GiftCardMall filter is active
            if self.config.filter_verification_enabled:
                filter_ok = await self.verify_filter(bot_entity)
                if not filter_ok:
                    logger.error("Restarted but filter verification failed")
                    return False

            logger.info("Telegram client restarted, navigated, and filter verified")
            return True
        except Exception as e:
            logger.error("Failed to restart Telegram client: %s", e)
            return False

    async def get_bot_entity(self):
        """Resolve the target bot username to an entity."""
        return await self._client.get_entity(self.config.target_bot)

    async def get_latest_message(self, bot_entity):
        """Get the most recent message from the bot."""
        async for msg in self._client.iter_messages(bot_entity, limit=1):
            return msg
        return None

    @staticmethod
    def _strip_emoji_prefix(text: str) -> str:
        """Remove leading emoji characters, variation selectors, and whitespace."""
        import unicodedata
        cleaned = text.lstrip()
        while cleaned:
            cat = unicodedata.category(cleaned[0])
            if cat.startswith("So") or cat.startswith("Mn") or cat.startswith("Mc") or cat == "Cf":
                cleaned = cleaned[1:]
            else:
                break
        return cleaned.lstrip()

    async def click_button_by_text(
        self,
        bot_entity,
        button_text: str,
        wait: float = 1.5,
        exact: bool = False,
    ) -> Optional[str]:
        """Find and click a button by its text, then return the updated message text.

        Args:
            exact: If True, require exact match after stripping emoji.
                   If False, allow substring match (safe for unique texts like Refresh).
        """
        msg = await self.get_latest_message(bot_entity)
        if not msg or not msg.buttons:
            return None

        search_lower = button_text.lower()
        for row in msg.buttons:
            for btn in row:
                btn_clean = self._strip_emoji_prefix(btn.text).lower()
                if exact:
                    matched = btn_clean == search_lower
                else:
                    matched = search_lower in btn_clean
                if matched:
                    await btn.click()
                    logger.info("Clicked button: '%s'", btn.text)
                    await asyncio.sleep(wait)
                    updated = await self.get_latest_message(bot_entity)
                    return updated.text if updated else None

        logger.warning("Button '%s' not found (exact=%s)", button_text, exact)
        return None

    def _has_button(self, msg, button_text: str) -> bool:
        """Check if a message contains a button matching the given text."""
        if not msg or not msg.buttons:
            return False
        search = button_text.lower()
        for row in msg.buttons:
            for btn in row:
                if search in self._strip_emoji_prefix(btn.text).lower():
                    return True
        return False

    async def navigate_to_listings(self, bot_entity) -> bool:
        """
        Navigate to the Listings view with GiftCardMall filter applied.
        Returns True if navigation succeeded.
        """
        logger.info("Navigating to Listings with GiftCardMall filter...")

        # Get the current message to decide how to reach the main menu.
        # IMPORTANT: Do NOT short-circuit just because a Refresh button is
        # visible — both unfiltered and filtered Listings show Refresh, so
        # we can't tell if the GiftCardMall filter is active. Always reset
        # and re-apply the filter.
        msg = await self.get_latest_message(bot_entity)

        # If Main Menu button is available, click it to get to a known state
        if self._has_button(msg, self.config.menu_button_text):
            result = await self.click_button_by_text(
                bot_entity, self.config.menu_button_text, wait=3.0, exact=True
            )
            if result is None:
                await self._client.send_message(bot_entity, "/start")
                await asyncio.sleep(3.0)
        else:
            # No Main Menu button — send /start to reset
            await self._client.send_message(bot_entity, "/start")
            await asyncio.sleep(3.0)

        # Now try to click Listing from the main menu
        result = await self.click_button_by_text(
            bot_entity, self.config.listings_button_text, wait=3.0, exact=True
        )
        if result is None:
            logger.error("Could not find Listings button")
            return False

        # Always apply the GiftCardMall filter (do not short-circuit even if
        # the Refresh button is visible — Listings shows all cards by default)
        # Try clicking Filters
        result = await self.click_button_by_text(
            bot_entity, self.config.filters_button_text, wait=3.0, exact=True
        )
        if result is None:
            logger.error("Could not find Filters button")
            return False

        # Select GiftCardMall filter
        result = await self.click_button_by_text(
            bot_entity, self.config.giftcardmall_filter_text, wait=5.0, exact=True
        )
        if result is None:
            logger.error("Could not find GiftCardMall filter")
            return False

        # Poll for listings screen (Refresh button) with retries
        # Increased from 5s to 15s — bot may need time to apply filter
        for attempt in range(15):
            await asyncio.sleep(1.0)
            msg = await self.get_latest_message(bot_entity)
            if self._has_button(msg, self.config.refresh_button_text):
                logger.info("On listings screen after filter selection (attempt %d)", attempt + 1)
                return True

        # Do NOT try "Back to Listings" / "Back" — that may cancel the filter.
        # Go straight to the /start → Listing fallback to reset to known state.
        logger.warning("Refresh button not found after 15s — falling back to /start → Listing")
        await self._client.send_message(bot_entity, "/start")
        await asyncio.sleep(3.0)
        result = await self.click_button_by_text(
            bot_entity, self.config.listings_button_text, wait=3.0, exact=True
        )
        if result is None:
            logger.error("Fallback: Could not find Listings button after /start")
            return False

        msg = await self.get_latest_message(bot_entity)
        if self._has_button(msg, self.config.refresh_button_text):
            logger.info("Successfully navigated to GiftCardMall listings via fallback")
            return True

        logger.error("Navigation failed — Refresh button not found")
        return False

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

    async def verify_filter(self, bot_entity) -> bool:
        """Do a test refresh and verify the GiftCardMall filter is active.
        Returns True if verified, False otherwise."""
        logger.info("Verifying filter is active...")

        # Do a test refresh to get the latest message
        text = await self.send_refresh(bot_entity)
        if text is None:
            logger.warning("Could not get message text for filter verification")
            return False

        verifier = FilterVerifier(self.config.giftcardmall_filter_text)
        is_ok = verifier.is_correct_filter(text)

        if is_ok:
            logger.info("Filter verified: %s", self.config.giftcardmall_filter_text)
        else:
            logger.warning(
                "Filter verification failed — expected '%s'",
                self.config.giftcardmall_filter_text,
            )

        return is_ok
