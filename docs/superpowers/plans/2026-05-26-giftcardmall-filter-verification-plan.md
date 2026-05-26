# GiftCardMall Filter Verification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add content-based filter verification so the scraper confirms the GiftCardMall filter is active before polling, with retry logic and frontend error reporting.

**Architecture:** A new `FilterVerifier` class parses the `Filters:` line from bot message text. `BotClient.verify_filter()` does a test refresh and delegates to the verifier. `main.py` orchestrates verification with retries before entering the poll loop.

**Tech Stack:** Python 3.12, Telethon, regex, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scraper/filter_verifier.py` | Create | Parse `Filters:` line from bot message text, compare to expected filter |
| `scraper/config.py` | Modify | Add `FILTER_VERIFICATION_RETRIES` and `FILTER_VERIFICATION_ENABLED` env vars |
| `scraper/bot_client.py` | Modify | Add `verify_filter()` method that refreshes and checks filter state |
| `scraper/main.py` | Modify | Integrate verification with retry loop before poll_loop |
| `tests/test_filter_verifier.py` | Create | Unit tests for `FilterVerifier` with sample bot messages |

---

### Task 1: Create `FilterVerifier`

**Files:**
- Create: `scraper/filter_verifier.py`
- Test: `tests/test_filter_verifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_filter_verifier.py
import pytest
from scraper.filter_verifier import FilterVerifier


class TestFilterVerifier:
    def test_extract_filter_giftcardmall(self):
        text = "Filters: GiftCardMall\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) == "GiftCardMall"

    def test_extract_filter_none(self):
        text = "Filters: None\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) == "None"

    def test_extract_filter_missing(self):
        text = "Page 1/3\nUpdated: 15:06"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) is None

    def test_is_correct_filter_true(self):
        text = "Filters: GiftCardMall\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is True

    def test_is_correct_filter_false(self):
        text = "Filters: None\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is False

    def test_is_correct_filter_missing_line(self):
        text = "Page 1/3\nUpdated: 15:06"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is False

    def test_case_insensitive(self):
        text = "Filters: giftcardmall\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is True

    def test_whitespace_handling(self):
        text = "Filters:   GiftCardMall  \nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) == "GiftCardMall"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vscode/projects/telegram-buyer && python -m pytest tests/test_filter_verifier.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.filter_verifier'`

- [ ] **Step 3: Write minimal implementation**

```python
# scraper/filter_verifier.py
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
        Returns the filter name, or None if the Filters line is not found."""
        match = self.FILTER_PATTERN.search(message_text)
        if match:
            return match.group(1)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vscode/projects/telegram-buyer && python -m pytest tests/test_filter_verifier.py -v`

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/vscode/projects/telegram-buyer
git add scraper/filter_verifier.py tests/test_filter_verifier.py
git commit -m "feat: add FilterVerifier for content-based filter verification"
```

---

### Task 2: Add Config Variables

**Files:**
- Modify: `scraper/config.py`

- [ ] **Step 1: Add new environment variables to `ScraperConfig`**

```python
# scraper/config.py — add to ScraperConfig.__init__
self.filter_verification_enabled: bool = (
    os.getenv("FILTER_VERIFICATION_ENABLED", "true").lower() == "true"
)
self.filter_verification_retries: int = int(
    os.getenv("FILTER_VERIFICATION_RETRIES", "3")
)
```

Insert after the existing `self.giftcardmall_filter_text` line.

- [ ] **Step 2: Verify config loads correctly**

Run: `cd /home/vscode/projects/telegram-buyer && python -c "from scraper.config import ScraperConfig; c = ScraperConfig(); print(f'enabled={c.filter_verification_enabled}, retries={c.filter_verification_retries}')"`

Expected: `enabled=True, retries=3` (or values from your `.env`)

- [ ] **Step 3: Commit**

```bash
cd /home/vscode/projects/telegram-buyer
git add scraper/config.py
git commit -m "feat: add FILTER_VERIFICATION_ENABLED and FILTER_VERIFICATION_RETRIES config"
```

---

### Task 3: Add `verify_filter()` to `BotClient`

**Files:**
- Modify: `scraper/bot_client.py`
- Modify: `scraper/__init__.py` (if needed for imports)

- [ ] **Step 1: Add import and `verify_filter()` method**

Add import at the top of `scraper/bot_client.py`:

```python
from .filter_verifier import FilterVerifier
```

Add the new method to `BotClient` class, after `go_back_to_listings()`:

```python
    async def verify_filter(self, bot_entity) -> bool:
        """Do a test refresh and verify the GiftCardMall filter is active.
        Returns True if verified, False otherwise."""
        logger.info("Verifying filter is active...")

        # Do a test refresh to get the latest message
        text = await self.send_refresh(bot_entity)
        if text is None:
            logger.warning("Could not get message text for filter verification")
            return False

        verifier = FilterVerifier(self.config.giftcardmall_filter_text)
        is_ok = verifier.is_correct_filter(text)

        if is_ok:
            logger.info("Filter verified: %s", self.config.giftcardmall_filter_text)
        else:
            logger.warning(
                "Filter verification failed — expected '%s'",
                self.config.giftcardmall_filter_text,
            )

        return is_ok
```

- [ ] **Step 2: Verify syntax**

Run: `cd /home/vscode/projects/telegram-buyer && python -c "import ast; ast.parse(open('scraper/bot_client.py').read()); print('Syntax OK')"`

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
cd /home/vscode/projects/telegram-buyer
git add scraper/bot_client.py
git commit -m "feat: add verify_filter() method to BotClient"
```

---

### Task 4: Integrate Verification into Startup Flow

**Files:**
- Modify: `scraper/main.py`

- [ ] **Step 1: Add import for FilterVerifier**

Add to imports at the top of `scraper/main.py`:

```python
from .filter_verifier import FilterVerifier
```

- [ ] **Step 2: Replace the navigation block with verification + retry logic**

Replace this block in `scraper/main.py` (around lines 45-50):

```python
    # Navigate to Listings with GiftCardMall filter
    nav_success = await bot_client.navigate_to_listings(bot_entity)
    if not nav_success:
        logger.warning("Navigation to listings failed — will try to refresh current view")
```

With:

```python
    # Navigate to Listings with GiftCardMall filter
    nav_success = await bot_client.navigate_to_listings(bot_entity)
    if not nav_success:
        logger.warning("Navigation to listings failed — will try to refresh current view")

    # Verify the filter is actually active (content-based check)
    if config.filter_verification_enabled:
        verifier = FilterVerifier(config.giftcardmall_filter_text)
        verified = False
        for attempt in range(1, config.filter_verification_retries + 1):
            verified = await bot_client.verify_filter(bot_entity)
            if verified:
                break
            logger.warning(
                "Filter verification failed (attempt %d/%d) — retrying navigation...",
                attempt,
                config.filter_verification_retries,
            )
            nav_success = await bot_client.navigate_to_listings(bot_entity)
            if not nav_success:
                logger.error("Navigation retry failed on attempt %d", attempt)

        if not verified:
            logger.error(
                "Filter verification failed after %d attempts — stopping scraper",
                config.filter_verification_retries,
            )
            if ws_client._connected:
                await ws_client.emit_scraper_state({
                    "state": "error",
                    "reason": "filter_verification_failed",
                })
            await bot_client.stop()
            sys.exit(1)
    else:
        logger.info("Filter verification disabled — skipping")
```

- [ ] **Step 3: Verify syntax**

Run: `cd /home/vscode/projects/telegram-buyer && python -c "import ast; ast.parse(open('scraper/main.py').read()); print('Syntax OK')"`

Expected: `Syntax OK`

- [ ] **Step 4: Run all scraper tests**

Run: `cd /home/vscode/projects/telegram-buyer && python -m pytest tests/ -v`

Expected: All tests PASS (including the new `test_filter_verifier.py`)

- [ ] **Step 5: Commit**

```bash
cd /home/vscode/projects/telegram-buyer
git add scraper/main.py
git commit -m "feat: integrate filter verification with retry logic into startup flow"
```

---

### Task 5: Update `.env` Template / Documentation

**Files:**
- Modify: `.env.example` (if exists) or README

- [ ] **Step 1: Document the new environment variables**

If `.env.example` exists, add:

```bash
# Filter verification (optional)
FILTER_VERIFICATION_ENABLED=true
FILTER_VERIFICATION_RETRIES=3
```

If no `.env.example`, add to `README.md` in the Configuration section.

- [ ] **Step 2: Commit**

```bash
cd /home/vscode/projects/telegram-buyer
git add .env.example README.md  # whichever was modified
git commit -m "docs: document FILTER_VERIFICATION_ENABLED and FILTER_VERIFICATION_RETRIES"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ `FilterVerifier` class with `extract_filter()` and `is_correct_filter()` — Task 1
- ✅ Config variables `FILTER_VERIFICATION_ENABLED` and `FILTER_VERIFICATION_RETRIES` — Task 2
- ✅ `BotClient.verify_filter()` method — Task 3
- ✅ Integration with retry loop in `main.py` — Task 4
- ✅ Error state emission to frontend — Task 4
- ✅ Unit tests — Task 1
- ✅ Documentation — Task 5

**2. Placeholder scan:** No TBD, TODO, or vague steps found.

**3. Type consistency:** `FilterVerifier` uses `Optional[str]` consistently. `verify_filter()` returns `bool`. Config types are `bool` and `int`. All consistent.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-26-giftcardmall-filter-verification-plan.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
