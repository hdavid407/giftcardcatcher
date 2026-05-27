"""Socket.IO event handlers for the Flask backend."""

import logging
from typing import Optional

from flask import request
from flask_socketio import SocketIO, emit

from .config import BackendConfig
from .store import MatchStore

logger = logging.getLogger(__name__)

_scraper_sid: Optional[str] = None


def _detect_client(req) -> str:
    """Detect whether the connecting client is the scraper or a frontend."""
    user_agent = req.headers.get("User-Agent", "")
    if "python" in user_agent.lower() or "aiohttp" in user_agent.lower():
        return "scraper"
    return "frontend"


def _check_api_key(req, config: BackendConfig) -> bool:
    """Validate the API key header if required."""
    if not config.api_key:
        return True
    return req.headers.get("X-API-Key") == config.api_key


def register_socketio_events(
    socketio: SocketIO,
    store: MatchStore,
    config: BackendConfig,
    process_manager: "ScraperProcessManager" = None,
):
    """Register all Socket.IO event handlers."""
    from .process_manager import ScraperProcessManager

    @socketio.on("connect")
    def on_connect(auth=None):
        """Handle client connection."""
        client_type = _detect_client(request)
        logger.info(
            "Socket.IO client connected: %s (%s)",
            request.sid,
            client_type,
        )

        global _scraper_sid
        if client_type == "scraper":
            _scraper_sid = request.sid
            logger.info("Scraper registered with SID: %s", _scraper_sid)

        # Send current scraper state to newly connected client
        state = store.get_scraper_state()
        emit("scraper_state", state)

        # Sync current cards and scrape count to newly connected clients
        latest_cards = store.get_latest_cards()
        if latest_cards:
            emit("cards_update", {"cards": latest_cards, "timestamp": 0})

        scrape_count = store.get_scrape_count()
        if scrape_count > 0:
            emit("scrape_count", {"count": scrape_count})

    @socketio.on("disconnect")
    def on_disconnect():
        logger.info("Socket.IO client disconnected: %s", request.sid)
        global _scraper_sid
        if request.sid == _scraper_sid:
            _scraper_sid = None
            logger.info("Scraper disconnected")

    @socketio.on("purchase_card")
    def on_purchase_card(data: dict):
        """
        Called when the frontend wants to purchase a specific card.
        Receives: { row_index: int }
        Relays to the scraper process.
        """
        row_index = data.get("row_index")
        if row_index is None:
            logger.warning("purchase_card received without row_index")
            return

        logger.info("Purchase request for row %d", row_index)

        if _scraper_sid:
            emit("purchase_card", {"row_index": row_index}, room=_scraper_sid)
            logger.info("Relayed purchase_card to scraper (row %d)", row_index)
        else:
            logger.warning("Scraper not connected — cannot relay purchase_card")
            emit("purchase_card_error", {
                "row_index": row_index,
                "reason": "Scraper not connected",
            })

    @socketio.on("scraper_state")
    def on_scraper_state(data: dict):
        """Receive scraper state updates and broadcast to frontends."""
        state = data.get("state", "unknown")
        reason = data.get("reason")
        store.set_scraper_state(state, reason)
        emit("scraper_state", data, broadcast=True)

    @socketio.on("status_update")
    def on_status_update(data: dict):
        """Receive status updates from scraper and broadcast."""
        emit("status_update", data, broadcast=True)

    @socketio.on("cards_update")
    def on_cards_update(data: dict):
        """Receive card list from scraper, store it, and broadcast."""
        cards = data.get("cards", [])
        store.set_latest_cards(cards)
        emit("cards_update", data, broadcast=True)

    @socketio.on("scrape_count")
    def on_scrape_count(data: dict):
        """Receive scrape count from scraper and broadcast."""
        emit("scrape_count", data, broadcast=True)

    @socketio.on("target_amount_changed")
    def on_target_amount_changed(data: dict):
        """Relay target amount changes."""
        emit("target_amount_changed", data, broadcast=True)

    @socketio.on("scraper_control")
    def on_scraper_control(data: dict):
        """Relay scraper control commands to the scraper."""
        if _scraper_sid:
            emit("scraper_control", data, room=_scraper_sid)
        else:
            logger.warning("Scraper not connected — cannot relay scraper_control")
