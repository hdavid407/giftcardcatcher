import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class FilterVerifier:
    """Parses the 'Filters:' line from bot message text to verify the active filter."""

    FILTER_PATTERN = re.compile(r"Filters:\s*(\S+)", re.IGNORECASE)

    def __init__(self, expected_filter: str):
        self.expected_filter = expected_filter.strip()

    def extract_filter(self, message_text: str) -> Optional[str]:
        """Extract the filter name from the bot message text.
        Returns the filter name, or None if the Filters line is not found.
        Strips backtick characters that Telegram uses for markdown formatting."""
        match = self.FILTER_PATTERN.search(message_text)
        if match:
            return match.group(1).strip("`'\"")
        return None

    def is_correct_filter(self, message_text: str) -> bool:
        """Return True if the message shows the expected filter is active."""
        actual = self.extract_filter(message_text)
        if actual is None:
            logger.warning("Filters line not found in message text")
            return False
        result = actual.lower() == self.expected_filter.lower()
        if not result:
            logger.warning(
                "Filter mismatch: expected '%s', got '%s'",
                self.expected_filter,
                actual,
            )
        return result
