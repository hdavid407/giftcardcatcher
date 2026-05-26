# GiftCardMall Filter Verification — Design Spec

**Date:** 2026-05-26
**Status:** Approved
**Goal:** Ensure the scraper never polls unfiltered gift card listings by verifying the GiftCardMall filter is actually active, using the bot's own "Filters: <name>" message text.

---

## 1. Problem

The scraper's `navigate_to_listings()` method navigates to the bot's Listings screen and attempts to apply the GiftCardMall filter. However, there is no verification that the filter was successfully applied. The bot may silently ignore the filter click, or the filter state may not persist across sessions. The scraper then polls and scrapes all gift cards from all sources, not just GiftCardMall.

**Evidence:** The bot message explicitly shows the active filter on every refresh:

```
Filters: None          ← unfiltered (wrong)
Filters: GiftCardMall  ← filtered (correct)
```

This text is a reliable, bot-native signal of filter state.

---

## 2. Solution Overview

After `navigate_to_listings()` completes, perform a **test refresh** and parse the bot message to read the `Filters:` line. If the filter does not match the expected value, retry the full navigation flow up to a configured maximum. If still failing, emit an error state to the frontend and stop polling.

---

## 3. Components

### 3.1 `FilterVerifier` (new file: `scraper/filter_verifier.py`)

A small, focused class with one job: given raw bot message text, extract the current filter name.

**Interface:**

```python
class FilterVerifier:
    def __init__(self, expected_filter: str):
        self.expected_filter = expected_filter

    def extract_filter(self, message_text: str) -> Optional[str]:
        """Parse the 'Filters: <name>' line from bot message text.
        Returns the filter name, or None if not found."""

    def is_correct_filter(self, message_text: str) -> bool:
        """Return True if the message shows the expected filter is active."""
```

**Parsing strategy:**
- Use a regex to match `Filters:\s*(\S+)` (case-insensitive)
- Handle edge cases: "Filters: None", missing line, extra whitespace

### 3.2 `BotClient` changes (`scraper/bot_client.py`)

Add a new method:

```python
async def verify_filter(self, bot_entity) -> bool:
    """Do a test refresh and verify the GiftCardMall filter is active.
    Returns True if verified, False otherwise."""
```

This method:
1. Calls `send_refresh(bot_entity)` to get the latest message
2. Passes the message text to `FilterVerifier.is_correct_filter()`
3. Logs the result for transparency

### 3.3 `main.py` changes (`scraper/main.py`)

After `navigate_to_listings()` succeeds, add a verification step before entering the poll loop:

```python
# Verify filter is actually active
verifier = FilterVerifier(config.giftcardmall_filter_text)
verified = await bot_client.verify_filter(bot_entity)
if not verified:
    # Retry navigation up to MAX_RETRIES
    ...
```

### 3.4 `ScraperConfig` changes (`scraper/config.py`)

Add new environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FILTER_VERIFICATION_RETRIES` | `3` | Max retry attempts if filter verification fails |
| `FILTER_VERIFICATION_ENABLED` | `true` | Toggle filter verification on/off |

---

## 4. Data Flow

### 4.1 Normal Startup (Filter Verified)

```
main.py
  └── navigate_to_listings() → True
  └── verify_filter()
        └── send_refresh() → get message text
        └── FilterVerifier.is_correct_filter() → True
  └── enter poll_loop()
```

### 4.2 Filter Not Applied (Retry Success)

```
main.py
  └── navigate_to_listings() → True
  └── verify_filter() → False
  └── retry navigate_to_listings() → True
  └── verify_filter() → True
  └── enter poll_loop()
```

### 4.3 Filter Still Wrong After Retries (Fatal)

```
main.py
  └── navigate_to_listings() → True
  └── verify_filter() → False (attempt 1/3)
  └── retry navigate_to_listings() → True
  └── verify_filter() → False (attempt 2/3)
  └── retry navigate_to_listings() → True
  └── verify_filter() → False (attempt 3/3)
  └── emit scraper_state: {state: "error", reason: "filter_verification_failed"}
  └── stop polling
```

---

## 5. Error Handling

| Scenario | Handling |
|----------|----------|
| `Filters:` line missing from message | Treat as unknown — log warning, retry navigation once |
| Filter shows `None` after navigation | Retry full navigation flow (max retries) |
| Still wrong after max retries | Emit error state to frontend, stop polling |
| Verification disabled via env var | Skip entirely, maintain backward compatibility |

---

## 6. Testing Strategy

- **Unit tests for `FilterVerifier`:** Test with sample message texts containing `Filters: GiftCardMall`, `Filters: None`, missing line, extra whitespace, case variations.
- **Integration test:** Mock `BotClient.send_refresh()` to return controlled message texts, verify retry logic and error emission.

---

## 7. Future Enhancements (Out of Scope)

- Periodic re-verification during long-running sessions (e.g., every 100 refreshes)
- Auto-detect filter name changes from the bot's filter button text

---

## 8. Approval

- Design: ✅ Approved
- Components: ✅ Approved
