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
    """Thread-safe in-memory store for the currently active match."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active: Optional[ActiveMatch] = None
        self._last_match_id: int = 0

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
