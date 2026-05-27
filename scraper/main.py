"""Telegram Gift Card Scraper — Entry point.

Orchestrates: connect Telethon → poll bot → parse cards → emit metrics.
Purchase commands arrive via WebSocket and execute immediately.
"""

import asyncio
import logging
import signal
import sys

from .bot_client import BotClient
from .config import ScraperConfig
from .filter_verifier import FilterVerifier
from .matcher import Matcher, GiftCardMatch
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

    # Verify the filter is actually active (content-based check)
    if config.filter_verification_enabled:
        verified = False
        for attempt in range(1, config.filter_verification_retries + 1):
            verified = await bot_client.verify_filter(bot_entity)
            if verified:
                break
            logger.warning(
                "Filter verification failed (attempt %d/%d) — retrying navigation...",
                attempt,
                config.filter_verification_retries,
            )
            nav_success = await bot_client.navigate_to_listings(bot_entity)
            if not nav_success:
                logger.error("Navigation retry failed on attempt %d", attempt)

        if not verified:
            logger.error(
                "Filter verification failed after %d attempts — stopping scraper",
                config.filter_verification_retries,
            )
            try:
                await ws_client.emit_scraper_state({
                    "state": "error",
                    "reason": "filter_verification_failed",
                })
            except Exception:
                pass
            await bot_client.stop()
            sys.exit(1)
    else:
        logger.info("Filter verification disabled — skipping")

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
        on_cards_update=ws_client.emit_cards_update if ws_client.is_connected else None,
        on_scrape_count=ws_client.emit_scrape_count if ws_client.is_connected else None,
        on_verified_match=ws_client.emit_verified_match if ws_client.is_connected else None,
    )

    # When the scraper reconnects to the backend, re-sync state
    async def on_reconnect():
        if refresher.is_user_paused():
            state = "paused"
        elif refresher.last_refresh is not None:
            state = "running"
        else:
            state = "unknown"
        await ws_client.emit_scraper_state({"state": state})
        if refresher.total_refreshes > 0:
            await ws_client.emit_scrape_count({"count": refresher.total_refreshes})
    ws_client.set_reconnect_handler(lambda: asyncio.create_task(on_reconnect()))

    # --- Purchase handler (new) ---

    async def handle_purchase(row_index: int):
        """Handle a purchase request from the frontend.

        NOTE: Purchase execution is currently disabled. The bot logs the
        request but does not click any buttons. Re-enable by uncommenting
        the purchaser.purchase() call below.
        """
        logger.info("Purchase REQUESTED for row %d (disabled — no action taken)", row_index)

        # Reconstruct a minimal GiftCardMatch for the purchaser
        # match = GiftCardMatch(
        #     row_index=row_index,
        #     card_number=None,
        #     card_text=f"row {row_index}",
        #     price=None,
        #     raw_message="",
        # )

        # try:
        #     success = await purchaser.purchase(match)
        #     if success:
        #         logger.info("Purchase at row %d completed successfully", row_index)
        #     else:
        #         logger.error("Purchase at row %d failed", row_index)
        # except Exception as e:
        #     logger.error("Purchase at row %d failed with exception: %s", row_index, e)
        # finally:
        #     # Always try to go back to listings
        #     try:
        #         await bot_client.go_back_to_listings(bot_entity)
        #     except Exception as e:
        #         logger.error("Failed to return to listings after purchase: %s", e)

    ws_client.set_purchase_handler(lambda row_index: asyncio.create_task(handle_purchase(row_index)))

    # --- Scraper control handler ---

    def on_control(action: str):
        """Handle pause/resume/restart commands from the frontend."""
        if action == "pause":
            refresher.pause_user()
            if ws_client.is_connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "paused"}))
        elif action == "resume":
            refresher.resume_user()
            if ws_client.is_connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "running"}))
        elif action == "restart":
            if ws_client.is_connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "restarting"}))

            async def do_restart():
                ok = await bot_client.restart()
                if ws_client.is_connected:
                    if ok:
                        await ws_client.emit_scraper_state({"state": "running"})
                    else:
                        await ws_client.emit_scraper_state({"state": "error", "reason": "restart failed"})
                else:
                    logger.warning("Backend not connected after restart — state not emitted")

            asyncio.create_task(do_restart())
        else:
            logger.warning("Unknown scraper control action: %s", action)

    ws_client.set_control_handler(on_control)

    async def on_refresh_text(text: str):
        """Called on each successful refresh. Parse and emit card metrics."""
        all_cards = matcher.parse_all_cards(text)
        await refresher.emit_scrape_metrics(all_cards)

        matches = matcher.find_matches(text)
        if matches:
            for match in matches:
                logger.info(
                    "🎯 $%.2f CARD DETECTED: %s (row %d)",
                    matcher.target_amount,
                    match.card_text,
                    match.row_index,
                )

            # Pause refresher and verify each match sequentially
            refresher.pause(60)
            if ws_client.is_connected:
                await ws_client.emit_scraper_state({"state": "verifying"})

            try:
                bot = await bot_client.get_bot_entity()
                for match in matches:
                    logger.info(
                        "🔍 Verifying registration for card at row %d...",
                        match.row_index,
                    )
                    is_unregistered = await bot_client.check_registration(
                        bot, match.row_index
                    )
                    if is_unregistered is True:
                        logger.info(
                            "✅ VERIFIED UNREGISTERED: row %d",
                            match.row_index,
                        )
                        # Build card data from the match
                        card_data = {
                            "card_number": match.card_number,
                            "bin": "unknown",
                            "amount": matcher.target_amount,
                            "currency": "USD",
                            "discount": None,
                            "button_row": match.row_index,
                            "is_match": True,
                            "raw_text": match.card_text,
                        }
                        if ws_client.is_connected:
                            await ws_client.emit_verified_match(card_data)
                    elif is_unregistered is False:
                        logger.info(
                            "❌ REGISTERED — skipping row %d",
                            match.row_index,
                        )
                    else:
                        logger.warning(
                            "⚠️ Could not determine registration for row %d",
                            match.row_index,
                        )
            except Exception as e:
                logger.error("Verification failed: %s", e)
            finally:
                refresher.resume()
                if ws_client.is_connected:
                    await ws_client.emit_scraper_state({"state": "running"})

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
