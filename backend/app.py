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
from .websocket import register_socketio_events

logger = logging.getLogger(__name__)


def create_app(config: BackendConfig) -> tuple[Flask, SocketIO, MatchStore, ScraperProcessManager]:
    """
    Create and configure the Flask application.

    Returns:
        (app, socketio, store, process_manager) tuple
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

    # Scraper subprocess manager
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    process_manager = ScraperProcessManager(project_root)

    # Register routes and events
    register_routes(app, store, socketio, config)
    register_socketio_events(socketio, store, config, process_manager)

    logger.info("Flask app created (CORS origins: %s)", config.cors_origins)

    return app, socketio, store, process_manager
