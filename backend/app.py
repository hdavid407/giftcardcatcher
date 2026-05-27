"""Flask application factory for the backend."""

import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from .config import BackendConfig
from .process_manager import ScraperProcessManager
from .store import MatchStore
from .routes import register_routes
from .websocket import register_socketio_events, _match_to_dict
from .timer import MatchTimer

logger = logging.getLogger(__name__)


def on_match_expire(match, socketio: SocketIO, store: MatchStore):
    """Called when a match expires. Broadcasts the event."""
    logger.info("Match %s expired, broadcasting", match.match_id)
    socketio.emit("match_expired", _match_to_dict(match))
    store.clear_match()


def create_app(config: BackendConfig) -> tuple[Flask, SocketIO, MatchStore, MatchTimer, ScraperProcessManager]:
    """
    Create and configure the Flask application.

    Returns:
        (app, socketio, store, timer, process_manager) tuple
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key

    # CORS
    CORS(app, origins=config.cors_origins)

    # Socket.IO
    socketio = SocketIO(
        app,
        cors_allowed_origins=config.cors_origins,
        async_mode="eventlet",
        logger=logger,
        engineio_logger=False,
    )

    # In-memory store
    store = MatchStore()

    # Match expiration timer
    timer = MatchTimer(
        store,
        on_expire=lambda m: on_match_expire(m, socketio, store),
    )
    timer.start()

    # Scraper subprocess manager
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    process_manager = ScraperProcessManager(project_root)

    # Register routes and events
    register_routes(app, store, socketio, config)
    register_socketio_events(socketio, store, config, process_manager)

    logger.info("Flask app created (CORS origins: %s)", config.cors_origins)

    return app, socketio, store, timer, process_manager
