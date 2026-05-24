"""Socket.IO event handlers for the Flask backend."""

import logging
from typing import Optional

from flask import request
from flask_socketio import SocketIO, emit

from .config import BackendConfig
from .discord_notifier import notify_match
from .store import MatchStore

logger = logging.getLogger(__name__)


def register_socketio_events(
    socketio: SocketIO,
    store: MatchStore,
    config: BackendConfig,
):
    """Register all Socket.IO event handlers."""

    @socketio.on("connect")
    def on_connect(auth=None):
        """Handle client connection."""
        client_type = _detect_client(request)
        logger.info(
            "Socket.IO client connected: %s (%s)",
            request.sid,
            client_type,
        )

        nonlocal _scraper_sid
        if client_type == "scraper":
            _scraper_sid = request.sid
            logger.info("Scraper registered with SID: %s", _scraper_sid)

        # If there's a pending match, send it to the newly connected client
        match = store.get_match()
        if match:
            emit("match_found", _match_to_dict(match))

        # Send current scraper state to newly connected client
        state = store.get_scraper_state()
        emit("scraper_state", state)

    @socketio.on("disconnect")
    def on_disconnect():
        logger.info("Socket.IO client disconnected: %s", request.sid)
        nonlocal _scraper_sid
        if request.sid == _scraper_sid:
            _scraper_sid = None
            logger.info("Scraper disconnected")

    @socketio.on("match_found")
    def on_match_found(data: dict):
        """
        Called when the scraper detects a match.
        Accepts: { row_index, card_text, price }
        Broadcasts the match to all connected clients.
        """
        card_text = data.get("card_text", "")
        row_index = data.get("row_index", 0)
        price = data.get("price")

        match = store.set_match(card_text, row_index, price, config.match_timeout)
        if match:
            logger.info("Match received and stored: %s", card_text)
            emit("match_found", _match_to_dict(match), broadcast=True)

            # Send Discord DM notification (fire-and-forget)
            match_data = {
                "row_index": row_index,
                "card_text": card_text,
                "price": price,
            }
            try:
                import asyncio
                asyncio.create_task(
                    notify_match(config.discord_bot_token, config.discord_user_id, match_data)
                )
            except Exception as e:
                logger.warning("Failed to queue Discord notification: %s", e)
        else:
            logger.warning("Match rejected — another match is already pending")
            emit("match_rejected", {
                "reason": "Another match is already pending",
                "card_text": card_text,
            })

    @socketio.on("status_update")
    def on_status_update(data: dict):
        """Called when the scraper sends a status update. Broadcasts to clients."""
        emit("status_update", data, broadcast=True)

    @socketio.on("cards_update")
    def on_cards_update(data: dict):
        """Called when the scraper sends the full card list. Broadcasts to clients."""
        nonlocal _scraper_sid
        _scraper_sid = request.sid
        cards = data.get("cards", [])
        store.set_latest_cards(cards)
        emit("cards_update", data, broadcast=True)
        logger.info("Cards update received: %d cards", len(cards))

    @socketio.on("scrape_count")
    def on_scrape_count(data: dict):
        """Called when the scraper sends the scrape count. Broadcasts to clients."""
        nonlocal _scraper_sid
        _scraper_sid = request.sid
        count = data.get("count", 0)
        store.set_scrape_count(count)
        emit("scrape_count", data, broadcast=True)

    # Track scraper SID for forwarding control commands
    _scraper_sid: Optional[str] = None

    @socketio.on("scraper_control")
    def on_scraper_control(data: dict):
        """Forward control commands from frontend to scraper."""
        action = data.get("action", "")
        logger.info("Scraper control received: %s", action)
        if _scraper_sid:
            emit("scraper_control", data, room=_scraper_sid)
        else:
            logger.warning("No scraper connected — cannot forward control")
            emit("scraper_state", {"state": "error", "reason": "scraper offline"})

    @socketio.on("scraper_state")
    def on_scraper_state(data: dict):
        """Receive state updates from scraper and broadcast to all clients."""
        store.set_scraper_state(data)
        emit("scraper_state", data, broadcast=True)
        logger.info("Scraper state updated: %s", data.get("state"))


def _match_to_dict(match) -> Optional[dict]:
    """Convert an ActiveMatch to a dict for JSON serialization."""
    if not match:
        return None
    return {
        "match_id": match.match_id,
        "card_text": match.card_text,
        "row_index": match.row_index,
        "price": match.price,
        "remaining_seconds": match.remaining_seconds,
        "status": match.status,
    }


def _check_api_key(req, config: BackendConfig) -> bool:
    """Validate the API key header against config."""
    api_key = req.headers.get("X-API-Key", "")
    return api_key == config.api_key


def _detect_client(req) -> str:
    """Try to determine if the client is the scraper or the frontend."""
    user_agent = req.headers.get("User-Agent", "")
    if "python-socketio" in user_agent:
        return "scraper"
    return "frontend"
