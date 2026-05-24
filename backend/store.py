"""In-memory match store. Thread-safe via a lock."""

import threading
import time
from typing import Optional

from dataclasses import dataclass


@dataclass
class ActiveMatch:
    """Represents a match that is pending user decision."""

    match_id: str
    card_text: str
    row_index: int
    price: Optional[str]
    discovered_at: float
    expires_at: float
    status: str = "pending"  # pending | approved | denied | expired

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.expires_at - time.time())


class MatchStore:
    """Thread-safe in-memory store for matches, cards, and metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active: Optional[ActiveMatch] = None
        self._last_match_id: int = 0
        self._scrape_count: int = 0
        self._latest_cards: list[dict] = []
        self._target_amount: float = 50.0
        self._scraper_state: dict = {"state": "unknown"}

    # --- Match methods ---

    def set_match(
        self,
        card_text: str,
        row_index: int,
        price: Optional[str],
        timeout: int,
    ) -> Optional[ActiveMatch]:
        """Store a new active match. Returns the match, or None if a match is already active."""
        with self._lock:
            if self._active and self._active.status == "pending":
                return None  # Already have a pending match

            self._last_match_id += 1
            now = time.time()
            match = ActiveMatch(
                match_id=f"match_{self._last_match_id}",
                card_text=card_text,
                row_index=row_index,
                price=price,
                discovered_at=now,
                expires_at=now + timeout,
                status="pending",
            )
            self._active = match
            return match

    def get_match(self) -> Optional[ActiveMatch]:
        """Get the current active match."""
        with self._lock:
            if self._active and self._active.status == "pending":
                # Check expiration
                if time.time() >= self._active.expires_at:
                    self._active.status = "expired"
                return self._active
            return None

    def approve_match(self) -> Optional[ActiveMatch]:
        """Approve the current pending match."""
        with self._lock:
            if self._active and self._active.status == "pending":
                self._active.status = "approved"
                return self._active
            return None

    def deny_match(self) -> Optional[ActiveMatch]:
        """Deny the current pending match."""
        with self._lock:
            if self._active and self._active.status == "pending":
                self._active.status = "denied"
                return self._active
            return None

    def clear_match(self):
        """Clear the active match."""
        with self._lock:
            self._active = None

    def has_pending(self) -> bool:
        """Check if there's a pending match."""
        with self._lock:
            return (
                self._active is not None
                and self._active.status == "pending"
                and time.time() < self._active.expires_at
            )

    # --- Metrics methods ---

    def set_scrape_count(self, count: int):
        """Update the total scrape count."""
        with self._lock:
            self._scrape_count = count

    def get_scrape_count(self) -> int:
        """Get the total scrape count."""
        with self._lock:
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

    def set_scraper_state(self, state: dict):
        """Update the scraper state."""
        with self._lock:
            self._scraper_state = state

    def get_scraper_state(self) -> dict:
        """Get the current scraper state."""
        with self._lock:
            return self._scraper_state.copy()
