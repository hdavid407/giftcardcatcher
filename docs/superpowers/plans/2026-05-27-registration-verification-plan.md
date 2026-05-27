# Registration Verification — Implementation Plan

## Overview

Implement the scraper-driven registration verification feature. When matches are found, the scraper clicks Purchase, reads the detail screen, clicks Cancel, and emits `verified_match` for unregistered cards. The frontend shows the Buy button only on verified cards.

## Files to Edit

### Scraper

1. **`scraper/bot_client.py`**
   - Add `click_cancel(bot_entity)` method to click Cancel/❌ Cancel on detail screen
   - Update `check_registration()` to call `click_cancel()` before returning, ensuring bot returns to listings

2. **`scraper/refresher.py`**
   - Add `_on_verified_match: Optional[Callable]` callback
   - `set_callbacks()` accepts `on_verified_match` parameter

3. **`scraper/ws_client.py`**
   - Add `emit_verified_match(card_data: dict)` method

4. **`scraper/main.py`**
   - In `on_refresh_text()`, after finding matches:
     - Pause refresher
     - For each match, call `check_registration()`
     - If True (unregistered), build card data and emit `verified_match`
     - Resume refresher

### Backend

5. **`backend/websocket.py`**
   - Add `verified_match` handler: receive from scraper, broadcast to all clients

### Frontend

6. **`frontend/hooks/useSocket.ts`**
   - Add `verifiedCards: Set<number>` state
   - Listen for `verified_match` event → add card_number to set
   - On `cards_update` → prune verified set to only card numbers still in listing
   - Expose `verifiedCards` in return type

7. **`frontend/components/CardGrid.tsx`**
   - Add `verifiedCards: Set<number>` prop
   - Buy button only when `item.is_match && verifiedCards.has(item.card_number)`
   - Non-verified matches show "⏳" or nothing

8. **`frontend/App.tsx`**
   - Extract `verifiedCards` from `useSocket()`
   - Pass `verifiedCards` prop to `CardGrid`

## Verification Steps

1. Restart all services
2. Trigger a match condition (set low target amount)
3. Confirm scraper pauses, verifies, resumes
4. Confirm frontend shows verified cards with Buy button
5. Confirm non-verified matches show no Buy button
