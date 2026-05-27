"""Telegram Gift Card Scraper — Entry point.

Orchestrates: connect Telethon → poll bot → parse cards → emit metrics.
Purchase commands arrive via WebSocket and execute immediately.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

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
        on_card_status=ws_client.emit_card_status if ws_client.is_connected else None,
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

    # --- Purchase flow handlers ---

    _pending_purchase_row: Optional[int] = None

    async def handle_initiate_purchase(row_index: int):
        """User clicked Buy — navigate to detail screen and emit preview."""
        nonlocal _pending_purchase_row
        _pending_purchase_row = row_index

        logger.info("Initiating purchase for row %d", row_index)
        refresher.pause(300)  # Long pause during purchase flow
        if ws_client.is_connected:
            await ws_client.emit_scraper_state({"state": "purchasing"})

        try:
            bot = await bot_client.get_bot_entity()
            success = await bot_client.click_purchase(bot, row_index)
            if not success:
                logger.error("Failed to click Purchase for row %d", row_index)
                if ws_client.is_connected:
                    await ws_client.emit_purchase_complete({
                        "card_number": None,
                        "success": False,
                        "reason": "click_purchase_failed",
                    })
                _pending_purchase_row = None
                refresher.resume()
                return

            await asyncio.sleep(2.0)
            details = await bot_client.read_card_details(bot)
            if details is None:
                logger.error("Could not read card details for row %d", row_index)
                if ws_client.is_connected:
                    await ws_client.emit_purchase_complete({
                        "card_number": None,
                        "success": False,
                        "reason": "read_details_failed",
                    })
                await bot_client.click_cancel(bot)
                _pending_purchase_row = None
                refresher.resume()
                return

            # Find card_number from matcher cache
            card_number = None
            for card in matcher._last_cards:
                if card.button_row == row_index:
                    card_number = card.card_number
                    break

            details["card_number"] = card_number
            details["button_row"] = row_index

            if ws_client.is_connected:
                await ws_client.emit_purchase_preview(details)
                logger.info("Emitted purchase_preview for row %d", row_index)

        except Exception as e:
            logger.error("Initiate purchase failed for row %d: %s", row_index, e)
            _pending_purchase_row = None
            refresher.resume()

    async def handle_confirm_purchase(row_index: int):
        """User confirmed purchase — click Confirm."""
        nonlocal _pending_purchase_row
        logger.info("Confirming purchase for row %d", row_index)

        try:
            bot = await bot_client.get_bot_entity()
            success = await bot_client.click_confirm(bot)
            if success:
                logger.info("Purchase confirmed for row %d", row_index)
            else:
                logger.error("Failed to click Confirm for row %d", row_index)

            await bot_client.go_back_to_listings(bot)

            card_number = None
            for card in matcher._last_cards:
                if card.button_row == row_index:
                    card_number = card.card_number
                    break

            if ws_client.is_connected:
                await ws_client.emit_purchase_complete({
                    "card_number": card_number,
                    "success": success,
                    "reason": None if success else "confirm_click_failed",
                })

        except Exception as e:
            logger.error("Confirm purchase failed for row %d: %s", row_index, e)
            if ws_client.is_connected:
                await ws_client.emit_purchase_complete({
                    "card_number": None,
                    "success": False,
                    "reason": "exception",
                })
        finally:
            _pending_purchase_row = None
            refresher.resume()

    async def handle_cancel_purchase(row_index: int):
        """User cancelled purchase — click Cancel."""
        nonlocal _pending_purchase_row
        logger.info("Cancelling purchase for row %d", row_index)

        try:
            bot = await bot_client.get_bot_entity()
            await bot_client.click_cancel(bot)
            logger.info("Cancelled purchase for row %d", row_index)

            card_number = None
            for card in matcher._last_cards:
                if card.button_row == row_index:
                    card_number = card.card_number
                    break

            if ws_client.is_connected:
                await ws_client.emit_purchase_complete({
                    "card_number": card_number,
                    "success": False,
                    "reason": "user_cancelled",
                })

        except Exception as e:
            logger.error("Cancel purchase failed for row %d: %s", row_index, e)
        finally:
            _pending_purchase_row = None
            refresher.resume()

    ws_client.set_initiate_purchase_handler(
        lambda row_index: asyncio.create_task(handle_initiate_purchase(row_index))
    )
    ws_client.set_confirm_purchase_handler(
        lambda row_index: asyncio.create_task(handle_confirm_purchase(row_index))
    )
    ws_client.set_cancel_purchase_handler(
        lambda row_index: asyncio.create_task(handle_cancel_purchase(row_index))
    )

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
        matcher._last_cards = all_cards
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
                        "🔍 Verifying card at row %d...",
                        match.row_index,
                    )
                    details = await bot_client.check_registration(
                        bot, match.row_index
                    )
                    if details is None:
                        logger.warning(
                            "⚠️ Could not verify card at row %d",
                            match.row_index,
                        )
                        continue

                    # Build the card_status payload
                    card_data = {
                        "card_number": match.card_number,
                        "status": details.get("status", "unknown"),
                        "id": details.get("id"),
                        "bin": details.get("bin") or "unknown",
                        "balance": details.get("balance"),
                        "price": details.get("price"),
                        "currency": details.get("currency", "USD"),
                        "rate": details.get("rate"),
                        "raw_text": match.card_text,
                        "button_row": match.row_index,
                    }

                    status_emoji = {"unregistered": "✅", "registered": "❌", "unknown": "⚠️"}
                    logger.info(
                        "%s Card #%s status: %s (id=%s, bin=%s, balance=%s, price=%s)",
                        status_emoji.get(card_data["status"], "?"),
                        card_data["card_number"],
                        card_data["status"],
                        card_data["id"],
                        card_data["bin"],
                        card_data["balance"],
                        card_data["price"],
                    )

                    if ws_client.is_connected:
                        await ws_client.emit_card_status(card_data)

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
