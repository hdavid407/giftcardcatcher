"""Entry point for the Flask backend server."""

import logging
import signal
import sys

from .app import create_app
from .config import BackendConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backend.run")


def main():
    logger.info("Starting Flask backend server")

    config = BackendConfig()
    app, socketio, store, timer, process_manager = create_app(config)

    logger.info("Listening on %s:%d", config.host, config.port)

    try:
        socketio.run(
            app,
            host=config.host,
            port=config.port,
            debug=False,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        timer.stop()
        process_manager.stop()


if __name__ == "__main__":
    main()
