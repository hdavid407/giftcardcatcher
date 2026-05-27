"""REST API routes for the Flask backend."""

import logging

from flask import Flask, request
from flask_socketio import SocketIO

from .config import BackendConfig
from .store import MatchStore
from .websocket import _check_api_key

logger = logging.getLogger(__name__)


def register_routes(app: Flask, store: MatchStore, socketio: SocketIO, config: BackendConfig):
    """Register all REST API routes."""

    @app.route("/api/status")
    def get_status():
        """Health check and current state."""
        return {
            "status": "running",
        }

    @app.route("/api/target_amount", methods=["POST"])
    def set_target_amount():
        """Update the target amount the scraper watches for."""
        if not _check_api_key(request, config):
            return {"error": "Unauthorized"}, 401

        data = request.get_json() or {}
        amount = data.get("amount")

        if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
            return {"error": "Invalid amount. Must be a positive number."}, 400

        store.set_target_amount(float(amount))
        logger.info("Target amount updated to %.2f", amount)

        # Notify the scraper
        socketio.emit("target_amount_changed", {"amount": float(amount)})

        return {"status": "updated", "target_amount": float(amount)}

    @app.route("/api/scraper/status")
    def get_scraper_status():
        """Get the current scraper state."""
        return store.get_scraper_state()

    @app.route("/api/debug/store")
    def debug_store():
        """Debug endpoint to inspect the store state."""
        return {
            "scrape_count": store.get_scrape_count(),
            "cards_count": len(store.get_latest_cards()),
            "latest_cards": store.get_latest_cards()[:3],  # first 3
        }
