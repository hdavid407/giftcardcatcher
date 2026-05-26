# GiftCardMall Filter Navigation Fix — Implementation Plan

## Goal

Remove the early-return in `navigate_to_listings()` that skips the GiftCardMall filter application when the Refresh button is visible after clicking "Listings".

## Plan

| Step | Task | File | Est. Time |
|------|------|------|-----------|
| 1 | Remove the early-return block after "Listings" click | `scraper/bot_client.py` | 5 min |
| 2 | Manual verification | Terminal | 10 min |
| 3 | Commit | - | 2 min |

---

## Step 1: Remove early-return block

**File:** `scraper/bot_client.py`

In `navigate_to_listings()`, delete this block (lines ~83-87):

```python
        # Check if we're now on listings (filter may persist)
        msg = await self.get_latest_message(bot_entity)
        if self._has_button(msg, self.config.refresh_button_text):
            logger.info("On listings screen after clicking Listing (filter persisted)")
            return True
```

After removal, the code after clicking "Listings" flows directly into the existing Filters → GiftCardMall logic.

## Step 2: Manual verification

1. Start the scraper: `python -m scraper.main`
2. Watch logs — verify the sequence:
   - "Clicked button: 'Listings'"
   - "Clicked button: 'Filters'"
   - "Clicked button: 'GiftCardMall'"
   - "Successfully navigated to GiftCardMall listings" or "On listings screen after filter selection"
3. Verify cards being scraped look like GiftCardMall cards (check BINs or card text in logs)

## Step 3: Commit

```
git add scraper/bot_client.py
git commit -m "fix: always apply GiftCardMall filter after navigation

Remove the early-return in navigate_to_listings() that skipped
filter application when the Refresh button was visible after
clicking 'Listings'. The unfiltered Listings view also shows
the Refresh button, so this check incorrectly returned early
without selecting the GiftCardMall filter."
```
