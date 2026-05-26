# GiftCardMall Filter Navigation Fix — Design Spec

**Date:** 2026-05-26
**Status:** Approved
**Goal:** Fix the scraper's navigation flow so the GiftCardMall filter is always applied before polling begins, preventing it from scraping non-GiftCardMall cards.

---

## 1. Problem

When starting the scraper, `navigate_to_listings()` in `bot_client.py` navigates to the bot's Listings screen but often fails to apply the GiftCardMall filter. The scraper then polls and scrapes all gift cards from all sources, not just GiftCardMall.

**Root cause:** After clicking the "Listings" button, the code checks for the presence of the Refresh button as a proxy for "listings loaded." Since the unfiltered Listings view also shows the Refresh button, this check succeeds immediately and the function returns `True` — never proceeding to the **Filters → GiftCardMall** navigation path. The filter is never selected.

---

## 2. Fix

**File:** `scraper/bot_client.py`
**Change:** Remove the early-return block in `navigate_to_listings()` that comes immediately after clicking the "Listings" button.

### Current flow (buggy)

```
/start → Main Menu → Listings
                        │
                        ▼
                 Refresh button visible? ──Yes──→ return True (filter NOT applied)
                        │
                       No
                        ▼
                  Filters → GiftCardMall → Back to Listings → return True
```

### Fixed flow

```
/start → Main Menu → Listings
                        │
                        ▼
                  Filters → GiftCardMall → Back to Listings → return True
```

### What is removed

```python
# Check if we're now on listings (filter may persist)
msg = await self.get_latest_message(bot_entity)
if self._has_button(msg, self.config.refresh_button_text):
    logger.info("On listings screen after clicking Listing (filter persisted)")
    return True
```

### What stays

- The initial check for "already on listings screen" at the top of the method — this still shortcuts when the scraper restarts while already on a properly filtered page (session file reuse).
- All existing filter-application logic: clicking Filters → GiftCardMall → polling for Refresh → Back to Listings fallback → ultimate `/start` fallback.
- The rest of the scraper is unchanged: polling, matching, purchasing, WebSocket, frontend — all untouched.

### Edge cases

| Case | Behavior |
|------|----------|
| Filter already active | Clicking Filters → GiftCardMall when GCM is already active is harmless; the button either stays selected or re-selects. |
| Filter selection screen needs "Back" | Existing fallback already polls for Refresh, then tries "Back to Listings" / "Back". |
| Filters button not found | Existing error handling returns `False`, scraper logs error and continues with warning (tries current view). |
| Restart mid-session | Initial check at top of method shortcuts if already on a filtered listings page. |

---

## 3. Scope

Single change in one file (`scraper/bot_client.py`). No configuration changes, no new dependencies, no frontend or backend changes.

---

## 4. Testing

1. **Manual test:** Start scraper with debug logging. Verify log shows: clicks Listings → clicks Filters → clicks GiftCardMall → sees Refresh button (filtered).
2. **Edge case — filter already active:** Manually apply GCM filter in bot, then start scraper. Verify it still navigates through filter path (harmless re-application).
3. **Edge case — navigation failure:** Temporarily break the filter button text config. Verify scraper logs error and falls back gracefully.
4. **Regression:** Verify polling, matching, purchase, WebSocket, and frontend all work as before.
