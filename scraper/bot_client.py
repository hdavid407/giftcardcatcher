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

    async def send_refresh(self, bot_entity) -> Optional[str]:
        """Send the Refresh inline button callback and return the updated message text."""
        from telethon.tl.custom.message import Message

        # Get the most recent message from the bot
        async for msg in self._client.iter_messages(bot_entity, limit=1):
            if not isinstance(msg, Message):
                continue

            # Try to find and click the Refresh button
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if self.config.refresh_button_text.lower() in btn.text.lower():
                            await btn.click()
                            logger.info("Clicked Refresh button")
                            # Wait for the bot to respond with updated data
                            await asyncio.sleep(1.5)
                            # Fetch the updated message
                            async for updated in self._client.iter_messages(bot_entity, limit=1):
                                return updated.text if hasattr(updated, "text") else None
        return None

    async def get_bot_entity(self):
        """Resolve the target bot username to an entity."""
        return await self._client.get_entity(self.config.target_bot)

    async def click_purchase(self, bot_entity, row_index: int) -> bool:
        """Click the Purchase button at the given row index."""
        async for msg in self._client.iter_messages(bot_entity, limit=1):
            if msg.buttons and len(msg.buttons) > row_index:
                # Purchase is typically the last button in a row
                row = msg.buttons[row_index]
                for btn in row:
                    if self.config.purchase_button_text.lower() in btn.text.lower():
                        await btn.click()
                        logger.info("Clicked Purchase button at row %d", row_index)
                        return True
        logger.warning("Could not find Purchase button at row %d", row_index)
        return False
