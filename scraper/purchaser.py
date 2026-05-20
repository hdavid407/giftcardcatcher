import logging
from typing import Optional

from .bot_client import BotClient
from .matcher import GiftCardMatch

logger = logging.getLogger(__name__)


class Purchaser:
    """Handles executing the purchase callback for a matched card."""

    def __init__(self, bot_client: BotClient):
        self.bot_client = bot_client
        self._last_result: Optional[bool] = None

    @property
    def last_result(self) -> Optional[bool]:
        return self._last_result

    async def purchase(self, match: GiftCardMatch) -> bool:
        """
        Execute the purchase for the given match.
        Returns True if the purchase callback was sent successfully.
        """
        logger.info(
            "Executing purchase for match at row %d: %s",
            match.row_index,
            match.card_text,
        )

        try:
            bot = await self.bot_client.get_bot_entity()
            success = await self.bot_client.click_purchase(bot, match.row_index)
            self._last_result = success

            if success:
                logger.info("Purchase callback sent successfully")
            else:
                logger.error("Failed to send purchase callback")

            return success
        except Exception as e:
            logger.error("Purchase failed with exception: %s", e)
            self._last_result = False
            return False
