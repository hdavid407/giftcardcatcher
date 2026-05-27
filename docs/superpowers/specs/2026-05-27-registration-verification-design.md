# Registration Verification — Design Spec

## Overview

When the scraper finds cards matching the target amount, it should verify whether each card is **unregistered** before showing the Buy button on the frontend. The scraper clicks Purchase, reads the card detail screen, clicks Cancel, and returns to listings. Only confirmed-unregistered cards get the Buy button.

Verified cards disappear from the frontend on the next refresh cycle if they are no longer listed.

## Architecture

The verification flow is scraper-driven with backend relay:

```
Scraper ──verified_match──► Backend ──verified_match──► Frontend (add to verified set)
   │                           │
   │                           │
Scraper ──cards_update──────► Backend ──cards_update──► Frontend (replace card list)
```

### Events

| Event | Direction | Payload | Purpose |
|-------|-----------|---------|---------|
| `verified_match` | Scraper → Backend | `{ card_number, bin, amount, currency, discount, button_row, raw_text }` | A card was verified unregistered |
| `verified_match` | Backend → Frontend | same as above | Frontend adds card to verified set |
| `cards_update` | Scraper → Backend | `{ cards: [...], timestamp }` | Full card list from latest refresh |
| `cards_update` | Backend → Frontend | same as above | Frontend replaces card list and prunes verified set |

## Scraper Changes

### 1. BotClient — add `click_cancel()`

After `check_registration()` reads the detail screen, the scraper needs to click Cancel and return to listings.

- Add `click_cancel(bot_entity)` method
- Clicks button text matching "Cancel" or "❌ Cancel"
- Waits briefly for the listing screen to return
- Returns success/failure

Update `check_registration()` to call `click_cancel()` before returning, ensuring the bot is back on the listings screen regardless of the registration result.

### 2. Refresher — add verification callback

- Add `_on_verified_match: Optional[Callable]` callback
- `set_callbacks()` accepts `on_verified_match` parameter

### 3. Scraper main loop — verify matches sequentially

In `on_refresh_text()`:

1. Parse all cards and emit metrics (unchanged)
2. Find amount matches via `matcher.find_matches()`
3. If matches found:
   - Pause the refresher (`refresher.pause(30)`)
   - For each match, call `bot_client.check_registration(bot, match.row_index)`
   - If result is `True` (unregistered):
     - Build card data and call `ws_client.emit_verified_match()`
   - After all matches checked, call `refresher.resume()`
   - Emit scraper state so frontend knows verification is done

The refresher remains paused during verification so the listing does not change underneath.

## Backend Changes

### websocket.py — relay `verified_match`

- Listen for `verified_match` from the scraper namespace
- Broadcast `verified_match` to all connected frontend clients

No storage in `MatchStore` — the frontend is the consumer.

## Frontend Changes

### useSocket.ts — track verified cards

- Add `verifiedCards: Set<number>` state (tracks `card_number`s)
- Listen for `verified_match` event: add `card_number` to `verifiedCards`
- On `cards_update`: replace `cards` list, then prune `verifiedCards` — keep only card numbers still present in the new `cards` list
- Expose `verifiedCards` in the hook return type

### CardGrid.tsx — show Buy only on verified

- Props now receive `verifiedCards: Set<number>`
- Buy button renders only when `item.is_match && verifiedCards.has(item.card_number)`
- Non-verified matches still highlight (e.g. yellow row) but show "⏳" or nothing in the Buy column

## Edge Cases

| Scenario | Handling |
|----------|----------|
| `check_registration()` returns `None` (unknown) | Treat as registered — do not emit verified_match |
| Bot ends up on wrong screen during verification | `go_back_to_listings()` already handles recovery; if that fails, resume polling and log error |
| User clicks Buy while verification is in progress | Purchase handler works independently; the Buy button only appears after verification anyway |
| Multiple matches on same refresh | Verified sequentially; each emits its own `verified_match` event |
| Match disappears before verification finishes | If Cancel returns to a listing without the card, it simply won't be in the next `cards_update` |
