"""REST API routes for the Flask backend."""

import logging

from flask import Flask, request
from flask_socketio import SocketIO

from .config import BackendConfig
from .store import MatchStore
from .websocket import _check_api_key, _match_to_dict

logger = logging.getLogger(__name__)


def register_routes(app: Flask, store: MatchStore, socketio: SocketIO, config: BackendConfig):
    """Register all REST API routes."""

    @app.route("/api/status")
    def get_status():
        """Health check and current state."""
        match = store.get_match()
        return {
            "status": "running",
            "has_pending_match": store.has_pending(),
            "active_match": _match_to_dict(match) if match else None,
        }

    @app.route("/api/approve", methods=["POST"])
    def approve_match():
        """Approve the current pending match."""
        if not _check_api_key(request, config):
            return {"error": "Unauthorized"}, 401

        match = store.approve_match()
        if match:
            logger.info("Match %s approved by user", match.match_id)
            socketio.emit("purchase_approved", _match_to_dict(match))
            return {"status": "approved", "match": _match_to_dict(match)}
        return {"error": "No pending match to approve"}, 404

    @app.route("/api/deny", methods=["POST"])
    def deny_match():
        """Deny the current pending match."""
        if not _check_api_key(request, config):
            return {"error": "Unauthorized"}, 401

        match = store.deny_match()
        if match:
            logger.info("Match %s denied by user", match.match_id)
            socketio.emit("purchase_denied", _match_to_dict(match))
            return {"status": "denied", "match": _match_to_dict(match)}
        return {"error": "No pending match to deny"}, 404

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
