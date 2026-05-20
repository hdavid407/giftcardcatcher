import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GiftCardMatch:
    """Represents a detected gift card that matches our criteria."""

    row_index: int
    card_text: str
    price: Optional[str]
    raw_message: str


class Matcher:
    """Parses the bot message text and detects target gift cards."""

    # Default target: $50 unregistered GiftCardMall
    # These can be overridden or made configurable
    TARGET_PATTERNS = [
        re.compile(r"\$?50.*unregister", re.IGNORECASE),
        re.compile(r"\$?50.*giftcard.?mall", re.IGNORECASE),
        re.compile(r"giftcard.?mall.*\$?50", re.IGNORECASE),
        re.compile(r"unregister.*\$?50", re.IGNORECASE),
    ]

    def __init__(self, custom_patterns: Optional[list[str]] = None):
        if custom_patterns:
            self.patterns = [re.compile(p, re.IGNORECASE) for p in custom_patterns]
        else:
            self.patterns = self.TARGET_PATTERNS

    def find_matches(self, message_text: str) -> list[GiftCardMatch]:
        """
        Parse the bot message text and return a list of matching gift cards.

        The bot typically returns text with inline buttons. We scan each line
        for target patterns. A 'line' is each newline-separated segment.
        """
        matches: list[GiftCardMatch] = []
        lines = message_text.split("\n")

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            if self._is_match(line):
                price = self._extract_price(line)
                match = GiftCardMatch(
                    row_index=idx,
                    card_text=line,
                    price=price,
                    raw_message=message_text,
                )
                matches.append(match)
                logger.info("Match found at line %d: %s", idx, line)

        return matches

    def _is_match(self, text: str) -> bool:
        """Check if text matches any of the target patterns."""
        for pattern in self.patterns:
            if pattern.search(text):
                return True
        return False

    @staticmethod
    def _extract_price(text: str) -> Optional[str]:
        """Extract a dollar amount from the text, if present."""
        match = re.search(r"\$?(\d+(?:\.\d{2})?)", text)
        if match:
            return f"${match.group(1)}"
        return None
