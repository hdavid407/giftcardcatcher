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
    matcher = Matcher(target_amount=50.0)
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

    bot_entity = await bot_client.get_bot_entity()

    # Navigate to Listings with GiftCardMall filter
    nav_success = await bot_client.navigate_to_listings(bot_entity)
    if not nav_success:
        logger.warning("Navigation to listings failed — will try to refresh current view")

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

    # Set up target amount change handler
    ws_client.set_target_amount_handler(matcher.set_target_amount)

    # Set up refresher callbacks for metrics
    refresher.set_callbacks(
        on_cards_update=ws_client.emit_cards_update if ws_client._connected else None,
        on_scrape_count=ws_client.emit_scrape_count if ws_client._connected else None,
    )

    # Set up scraper control handler
    def on_control(action: str):
        """Handle pause/resume/restart commands from the frontend."""
        if action == "pause":
            refresher.pause_user()
            if ws_client._connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "paused"}))
        elif action == "resume":
            refresher.resume_user()
            if ws_client._connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "running"}))
        elif action == "restart":
            if ws_client._connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "restarting"}))

            async def do_restart():
                ok = await bot_client.restart()
                if ws_client._connected:
                    if ok:
                        await ws_client.emit_scraper_state({"state": "running"})
                    else:
                        await ws_client.emit_scraper_state({"state": "error", "reason": "restart failed"})

            asyncio.create_task(do_restart())
        else:
            logger.warning("Unknown scraper control action: %s", action)

    ws_client.set_control_handler(on_control)

    async def on_refresh_text(text: str):
        """Called on each successful refresh. Parse and act on matches."""
        nonlocal matcher, refresher, ws_client, purchaser, config, bot_entity, bot_client

        # Parse ALL cards and emit metrics
        all_cards = matcher.parse_all_cards(text)
        await refresher.emit_scrape_metrics(all_cards)

        matches = matcher.find_matches(text)
        if not matches:
            return

        for match in matches:
            logger.info(
                "🎯 $%.2f CARD DETECTED: %s (row %d)",
                matcher.target_amount,
                match.card_text,
                match.row_index,
            )

            # Step 1: Click Purchase to check registration status
            logger.info("Checking registration status by clicking Purchase...")
            is_unregistered = await bot_client.check_registration(
                bot_entity, match.row_index
            )

            if is_unregistered is False:
                # Card is registered — not our target
                logger.info("Card is REGISTERED — skipping")
                await bot_client.go_back_to_listings(bot_entity)
                continue

            if is_unregistered is None:
                # Could not determine status — alert user anyway for manual check
                logger.warning("Could not determine registration — alerting user for manual verification")

            # Card is unregistered (or status unknown) — this is our target!
            logger.info(
                "✅ UNREGISTERED $%.2f CARD CONFIRMED: %s",
                matcher.target_amount,
                match.card_text,
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
                # No backend — auto-deny after timeout
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

            # Go back to listings and resume polling
            await bot_client.go_back_to_listings(bot_entity)
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
