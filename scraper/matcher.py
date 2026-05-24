import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GiftCardMatch:
    """Represents a detected gift card that matches our criteria."""

    row_index: int
    card_number: Optional[int]
    card_text: str
    price: Optional[str]
    raw_message: str


@dataclass
class CardInfo:
    """Represents any card shown in the bot listing."""

    card_number: int
    bin: str
    amount: float
    currency: str
    discount: Optional[int]
    button_row: int
    is_match: bool
    raw_text: str


class Matcher:
    """Parses the bot message text and detects target gift cards."""

    # Target: $50 cards (we'll verify unregistered status by clicking Purchase)
    TARGET_AMOUNT = 50.0

    def __init__(self, target_amount: Optional[float] = None):
        self.target_amount = target_amount or self.TARGET_AMOUNT

    def set_target_amount(self, amount: float):
        """Update the target amount dynamically."""
        logger.info("Target amount changed: %.2f → %.2f", self.target_amount, amount)
        self.target_amount = amount

    def parse_all_cards(self, message_text: str) -> list[CardInfo]:
        """
        Parse the bot message text and return ALL cards, not just matches.

        The bot format is:
        `1.` `420495xx` USD`$940.52` `at` `39%`
        """
        cards: list[CardInfo] = []
        lines = message_text.split("\n")

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            card_number = self._extract_card_number(line)
            if card_number is None:
                continue

            amount = self._extract_amount(line)
            if amount is None:
                continue

            bin_code = self._extract_bin(line)
            currency = self._extract_currency(line)
            discount = self._extract_discount(line)
            is_match = abs(amount - self.target_amount) < 0.01

            # Inline keyboard rows are offset by 2 in this bot layout
            button_row = card_number + 1

            card = CardInfo(
                card_number=card_number,
                bin=bin_code or "unknown",
                amount=amount,
                currency=currency or "USD",
                discount=discount,
                button_row=button_row,
                is_match=is_match,
                raw_text=line,
            )
            cards.append(card)

        return cards

    def find_matches(self, message_text: str) -> list[GiftCardMatch]:
        """
        Parse the bot message text and return a list of matching gift cards.
        """
        matches: list[GiftCardMatch] = []
        lines = message_text.split("\n")

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            card_number = self._extract_card_number(line)
            if card_number is None:
                continue

            amount = self._extract_amount(line)
            if amount is not None and abs(amount - self.target_amount) < 0.01:
                row_index = card_number + 1
                price = self._extract_price(line)
                match = GiftCardMatch(
                    row_index=row_index,
                    card_number=card_number,
                    card_text=line,
                    price=price,
                    raw_message=message_text,
                )
                matches.append(match)
                logger.info(
                    "🎯 $%.2f card found at line %d (card #%d => button row %d): %s",
                    amount,
                    idx,
                    card_number,
                    row_index,
                    line,
                )

        return matches

    @staticmethod
    def _extract_amount(text: str) -> Optional[float]:
        """Extract the USD amount from a card listing line."""
        # Look for patterns like USD`$50.00` or `$50.00`
        match = re.search(r"USD`?\$(\d+(?:\.\d{2})?)`?", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        # Fallback: any $amount
        match = re.search(r"\$(\d+(?:\.\d{2})?)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_price(text: str) -> Optional[str]:
        """Extract a dollar amount from the text, if present."""
        match = re.search(r"\$?(\d+(?:\.\d{2})?)", text)
        if match:
            return f"${match.group(1)}"
        return None

    @staticmethod
    def _extract_bin(text: str) -> Optional[str]:
        """Extract the masked BIN code like `420495xx`."""
        match = re.search(r"`(\d{4,6}[xX]{2,4})`", text)
        if match:
            return match.group(1)
        # Fallback: any digits followed by x's
        match = re.search(r"(\d+[xX]+)", text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_currency(text: str) -> Optional[str]:
        """Extract currency code like USD, AUD."""
        match = re.search(r"([A-Z]{3})`?\$", text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_discount(text: str) -> Optional[int]:
        """Extract discount percentage like `39%`."""
        match = re.search(r"`(\d+)%`", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_card_number(text: str) -> Optional[int]:
        """Extract the leading card ordinal (e.g., `1.`) from a listing line."""
        match = re.match(r"`?(\d+)\." , text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None
