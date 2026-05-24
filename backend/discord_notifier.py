"""Discord DM notifier for gift card match alerts."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Connects to Discord on-demand to send DM notifications."""

    def __init__(self, bot_token: str, user_id: int):
        self.bot_token = bot_token
        self.user_id = user_id

    async def send_match_notification(self, match_data: dict) -> bool:
        """
        Send a Discord DM embed with match details.

        Args:
            match_data: dict with keys like row_index, card_text, price, bin, amount, discount

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        sent = False

        @client.event
        async def on_ready():
            nonlocal sent
            try:
                user = await client.fetch_user(self.user_id)
                if user is None:
                    logger.warning("Discord user %s not found", self.user_id)
                    await client.close()
                    return

                dm_channel = await user.create_dm()
                embed = self._build_embed(match_data)
                await dm_channel.send(embed=embed)
                logger.info("Discord match notification sent to user %s", self.user_id)
                sent = True
            except discord.Forbidden:
                logger.warning("Cannot send DM to Discord user %s (DMs disabled)", self.user_id)
            except discord.HTTPException as e:
                logger.warning("Discord HTTP error sending notification: %s", e)
            except Exception as e:
                logger.warning("Unexpected error sending Discord notification: %s", e)
            finally:
                await client.close()

        try:
            await client.start(self.bot_token)
        except discord.LoginFailure:
            logger.error("Discord bot token is invalid")
            await client.close()
            return False
        except Exception as e:
            logger.warning("Discord client error: %s", e)
            await client.close()
            return False

        return sent

    def _build_embed(self, match_data: dict) -> discord.Embed:
        """Build a rich embed for the match notification."""
        embed = discord.Embed(
            title="🎯 Gift Card Match Found!",
            description="A card matching your target criteria was detected.",
            color=0x00FF00,
            timestamp=datetime.now(timezone.utc),
        )

        # Extract fields from match_data with fallbacks
        card_text = match_data.get("card_text", "N/A")
        price = match_data.get("price", "N/A")
        row_index = match_data.get("row_index", "N/A")

        # Try to parse BIN from card_text if available
        bin_value = match_data.get("bin", "N/A")
        amount = match_data.get("amount", "N/A")
        discount = match_data.get("discount", "N/A")

        embed.add_field(name="BIN", value=f"`{bin_value}`", inline=True)
        embed.add_field(name="Amount", value=f"`{amount}`", inline=True)
        embed.add_field(name="Discount", value=f"`{discount}`", inline=True)
        embed.add_field(name="Row", value=f"`#{row_index}`", inline=True)
        embed.add_field(name="Price", value=f"`{price}`", inline=True)

        if card_text and card_text != "N/A":
            embed.add_field(name="Card Details", value=f"```{card_text[:500]}```", inline=False)

        embed.set_footer(text="Telegram Gift Card Buyer")
        return embed


async def notify_match(bot_token: Optional[str], user_id: Optional[int], match_data: dict) -> bool:
    """
    Convenience function: send a Discord DM if config is present.

    Returns True if sent, False if skipped or failed.
    """
    if not bot_token or not user_id:
        logger.debug("Discord notification skipped: missing token or user_id")
        return False

    notifier = DiscordNotifier(bot_token, user_id)
    return await notifier.send_match_notification(match_data)
