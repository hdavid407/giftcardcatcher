"""Countdown timer that expires matches and cleans up state.

Uses a background thread instead of asyncio for Flask compatibility.
"""

import logging
import threading
import time
from typing import Callable, Optional

from .store import MatchStore, ActiveMatch

logger = logging.getLogger(__name__)


class MatchTimer:
    """Background thread that monitors active matches and expires them."""

    def __init__(self, store: MatchStore, on_expire: Callable[[ActiveMatch], None]):
        self.store = store
        self._on_expire = on_expire
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, check_interval: float = 2.0):
        """Start the timer loop in a background thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            args=(check_interval,),
            daemon=True,
        )
        self._thread.start()
        logger.info("Match timer started (interval=%.1fs)", check_interval)

    def _loop(self, check_interval: float):
        """Monitor loop running in background thread."""
        while self._running:
            time.sleep(check_interval)
            try:
                match = self.store.get_match()
                if match and match.status == "expired":
                    logger.info("Match %s expired", match.match_id)
                    try:
                        self._on_expire(match)
                    except Exception as e:
                        logger.error("Error in expire callback: %s", e)
            except Exception as e:
                logger.error("Timer check error: %s", e)

    def stop(self):
        """Signal the timer loop to stop."""
        self._running = False
        logger.info("Match timer stopped")
