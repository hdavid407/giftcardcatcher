import asyncio
import logging
import re
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
            if nav_ok:
                logger.info("Telegram client restarted and navigated successfully")
                return True
            else:
                logger.error("Restarted but navigation to listings failed")
                return False
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
        for attempt in range(5):
            await asyncio.sleep(1.0)
            msg = await self.get_latest_message(bot_entity)
            if self._has_button(msg, self.config.refresh_button_text):
                logger.info("On listings screen after filter selection")
                return True

        # Try Back to Listings
        result = await self.click_button_by_text(
            bot_entity, "Back to Listings", wait=3.0, exact=True
        )
        if result is None:
            result = await self.click_button_by_text(bot_entity, "Back", wait=2.0, exact=True)

        # Final verification
        msg = await self.get_latest_message(bot_entity)
        if self._has_button(msg, self.config.refresh_button_text):
            logger.info("Successfully navigated to GiftCardMall listings")
            return True

        # Ultimate fallback: filter persists across sessions
        logger.warning("Navigation stuck — falling back to /start → Listing")
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

    async def is_on_listings_screen(self, bot_entity) -> bool:
        """Check whether the current message shows the listings screen (has Refresh button)."""
        msg = await self.get_latest_message(bot_entity)
        return self._has_button(msg, self.config.refresh_button_text)

    async def send_refresh(self, bot_entity) -> Optional[str]:
        """Send the Refresh inline button callback and return the updated message text."""
        result = await self.click_button_by_text(
            bot_entity, self.config.refresh_button_text, wait=1.5
        )
        if result is None:
            # Diagnostic: log what screen we're actually on
            msg = await self.get_latest_message(bot_entity)
            if msg:
                preview = (msg.text or "[no text]").replace("\n", " ")[:150]
                has_buttons = bool(msg.buttons)
                logger.warning(
                    "Refresh failed — bot not on listings screen. "
                    "Preview: '%s...' | Has buttons: %s",
                    preview,
                    has_buttons,
                )
            else:
                logger.warning("Refresh failed — no message from bot")
        return result

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

    async def check_registration(self, bot_entity, row_index: int) -> Optional[dict]:
        """
        Click Purchase on a card, read its details, and return to listings.
        Returns the details dict, or None on failure.
        Always clicks Cancel and returns to the listings view before returning.
        """
        success = await self.click_purchase(bot_entity, row_index)
        if not success:
            return None

        # Wait for the detail view to load
        await asyncio.sleep(2.0)

        details = await self.read_card_details(bot_entity)
        try:
            await self.click_cancel(bot_entity)
        except Exception:
            logger.exception("Failed to click Cancel after reading details")
        return details

    async def read_card_details(self, bot_entity) -> Optional[dict]:
        """Read the purchase detail screen and extract structured card details.

        Assumes the bot is already on the detail screen.
        Returns a dict with keys: id, bin, balance, price, currency, rate, status, raw_text.
        Returns None if the detail screen cannot be read.
        """
        msg = await self.get_latest_message(bot_entity)
        if not msg or not msg.text:
            return None

        if not self._has_button(msg, "Cancel") and not self._has_button(msg, "Confirm"):
            logger.warning("read_card_details: not on detail screen")
            return None

        raw_text = msg.text
        logger.info("Reading card details from text: %s", raw_text[:200])

        details: dict = {
            "id": None,
            "bin": None,
            "balance": None,
            "price": None,
            "currency": "USD",
            "rate": None,
            "status": "unknown",
            "raw_text": raw_text,
        }

        id_match = re.search(r"ID:\s*`?(\d+)`?", raw_text)
        if id_match:
            details["id"] = id_match.group(1)

        bin_match = re.search(r"BIN:\s*`?([\dxX]+)`?", raw_text)
        if bin_match:
            details["bin"] = bin_match.group(1)

        balance_match = re.search(r"(?:Amount|Balance):\s*`?\$?(\d+(?:\.\d{1,2})?)`?", raw_text)
        if balance_match:
            details["balance"] = float(balance_match.group(1))

        price_match = re.search(r"Price:\s*`?\$?(\d+(?:\.\d{1,2})?)`?", raw_text)
        if price_match:
            details["price"] = float(price_match.group(1))

        rate_match = re.search(r"Rate:\s*`?(\d+)%`?", raw_text)
        if rate_match:
            details["rate"] = int(rate_match.group(1))

        text_lower = raw_text.lower()
        if "unregistered" in text_lower or "un-register" in text_lower:
            details["status"] = "unregistered"
        elif "registered" in text_lower:
            details["status"] = "registered"
        else:
            details["status"] = "unknown"

        logger.info("Parsed card details: %s", details)
        return details

    async def click_confirm(self, bot_entity) -> bool:
        """Click the ✅ Confirm button on the purchase detail screen."""
        confirm_texts = ["Confirm", "✅ Confirm", "✔️ Confirm", "Buy"]
        for text in confirm_texts:
            result = await self.click_button_by_text(bot_entity, text, wait=1.5)
            if result is not None:
                logger.info("Clicked confirm button: '%s'", text)
                return True

        logger.warning("Could not find Confirm button")
        return False

    async def click_cancel(self, bot_entity) -> bool:
        """Click the Cancel button on the purchase detail screen and return to listings."""
        cancel_texts = ["Cancel", "❌ Cancel", "✖️ Cancel", "Close"]
        for text in cancel_texts:
            result = await self.click_button_by_text(bot_entity, text, wait=1.5)
            if result is not None:
                logger.info("Clicked cancel button: '%s'", text)
                return True

        # Fallback: try Back
        back_ok = await self.go_back_to_listings(bot_entity)
        return back_ok

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
