"""Telegram Gift Card Scraper — Entry point.

Orchestrates: connect Telethon → poll bot → parse cards → match → notify → wait for approval → purchase.
"""

import asyncio
import logging
import signal
import sys

from .bot_client import BotClient
from .config import ScraperConfig
from .matcher import Matcher
from .purchaser import Purchaser
from .refresher import Refresher
from .ws_client import ScraperWSClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scraper.main")

# Global references for signal handler
_shutdown = False
_refresher: Refresher = None


def _signal_handler(sig, frame):
    global _shutdown
    logger.info("Received signal %s, shutting down...", sig)
    _shutdown = True
    if _refresher:
        _refresher.stop()


async def main():
    global _refresher

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("Starting Telegram Gift Card Scraper")

    config = ScraperConfig()
    matcher = Matcher()
    bot_client = BotClient(config)
    refresher = Refresher(bot_client, config)
    purchaser = Purchaser(bot_client)
    ws_client = ScraperWSClient(config)

    _refresher = refresher

    # Connect to Telegram
    try:
        await bot_client.start()
    except Exception as e:
        logger.error("Failed to start Telegram client: %s", e)
        sys.exit(1)

    # Connect to Flask backend
    try:
        await ws_client.connect()
        logger.info("Connected to backend")
    except Exception as e:
        logger.warning(
            "Could not connect to backend at %s: %s",
            config.backend_url,
            e,
        )
        logger.warning("Running without backend — matches will be logged only")

    async def on_refresh_text(text: str):
        """Called on each successful refresh. Parse and act on matches."""
        nonlocal matcher, refresher, ws_client, purchaser, config

        matches = matcher.find_matches(text)
        if not matches:
            return

        for match in matches:
            logger.info(
                "TARGET CARD DETECTED: %s (row %d)",
                match.card_text,
                match.row_index,
            )

            # Notify backend
            if ws_client._connected:
                await ws_client.emit_match(match)
            else:
                logger.info("Backend offline — logged match only")

            # Pause refresher while waiting for approval
            refresher.pause(config.match_timeout + 10)

            # Wait for user decision or timeout
            if ws_client._connected:
                decision = await ws_client.wait_for_approval(config.match_timeout)
            else:
                # No backend — auto-deny after timeout so printing doesn't block
                logger.info("No backend — skipping purchase for %s", match.card_text)
                decision = False

            if decision is True:
                logger.info("User APPROVED purchase for %s", match.card_text)
                success = await purchaser.purchase(match)
                if success:
                    logger.info("Purchase executed successfully!")
                else:
                    logger.error("Purchase failed!")
            elif decision is False:
                logger.info("User DENIED purchase for %s", match.card_text)
            else:
                logger.info("Match expired — no action taken for %s", match.card_text)

            # Resume polling
            refresher.resume()

    # Start the polling loop
    logger.info("Starting poll loop for bot: %s", config.target_bot)
    await refresher.poll_loop(on_refresh_text)

    # Cleanup
    await ws_client.disconnect()
    await bot_client.stop()
    logger.info("Scraper shut down")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting")
