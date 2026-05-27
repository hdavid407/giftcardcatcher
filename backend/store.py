"""In-memory match store. Thread-safe via a lock."""

import threading
from typing import Optional


class MatchStore:
    """Thread-safe in-memory store for cards, metrics, and scraper state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._scrape_count: int = 0
        self._latest_cards: list[dict] = []
        self._target_amount: float = 50.0
        self._scraper_state: dict = {"state": "unknown"}

    # --- Card / metrics methods ---

    def get_scrape_count(self) -> int:
        """Get the total number of scrapes performed."""
        with self._lock:
            return self._scrape_count

    def increment_scrape_count(self) -> int:
        """Increment the scrape count. Returns the new count."""
        with self._lock:
            self._scrape_count += 1
            return self._scrape_count

    def set_latest_cards(self, cards: list[dict]):
        """Update the latest card list from the most recent refresh."""
        with self._lock:
            self._latest_cards = cards

    def get_latest_cards(self) -> list[dict]:
        """Get the latest card list."""
        with self._lock:
            return self._latest_cards.copy()

    def set_target_amount(self, amount: float):
        """Update the target amount."""
        with self._lock:
            self._target_amount = amount

    def get_target_amount(self) -> float:
        """Get the current target amount."""
        with self._lock:
            return self._target_amount

    # --- Scraper state methods ---

    def set_scraper_state(self, state: str, reason: str = None):
        """Update the scraper state."""
        with self._lock:
            self._scraper_state = {"state": state}
            if reason:
                self._scraper_state["reason"] = reason

    def get_scraper_state(self) -> dict:
        """Get the current scraper state."""
        with self._lock:
            return dict(self._scraper_state)
