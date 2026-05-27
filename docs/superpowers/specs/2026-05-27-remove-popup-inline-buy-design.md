# Remove Match Popup — Replace with Inline Buy Buttons

**Date**: 2026-05-27
**Status**: Draft

## Overview

Replace the modal "Buy Now / Skip" popup (`MatchAlert` component) with inline Buy buttons on matched cards in the card grid. Uses direct WebSocket commands (`purchase_card`) instead of the match/approve/deny state machine. The scraper no longer pauses polling while waiting for user input — purchases happen asynchronously while refreshing continues.

## What Gets Removed

- `frontend/components/MatchAlert.tsx` — entire file
- `backend/timer.py` — entire file (match expiration monitor, no longer needed)
- `MatchStore` match state machine (`ActiveMatch`, `set_match`, `get_match`, `approve_match`, `deny_match`, `clear_match`, `has_pending`)
- `POST /api/approve` and `POST /api/deny` REST endpoints
- `wait_for_approval()` on the scraper WS client
- Polling pause during match handling in `main.py`
- All match-related WebSocket events: `match_found`, `match_rejected`, `purchase_approved`, `purchase_denied`, `match_expired`
- Discord DM notification on match (was triggered from `on_match_found`)

## What Gets Added

- Buy button on matched card rows in `CardGrid`
- `purchase_card` WebSocket event: `{ row_index: number }`
- Scraper `purchase_card` handler that buys immediately
- `sendPurchase(row_index)` function in `useSocket` hook
- Purchase feedback via the existing log stream

## New Data Flow

```
User clicks "Buy" on card row #3
  → Frontend emits "purchase_card" { row_index: 3 }
  → Backend relays "purchase_card" { row_index: 3 } to scraper
  → Scraper clicks Purchase button at inline keyboard row 3
  → Scraper goes back to listings
  → Scraper emits purchase result log
  → Frontend shows result in log stream
```

## Frontend Changes

### `CardGrid.tsx`
- Add `onBuyCard: (row_index: number) => void` prop
- Add "Buy" column header in the table header row
- On each card row where `item.is_match === true`, render a `💰` button
- Button calls `onBuyCard(item.button_row)` — uses `button_row` (not `card_number`) because that's the inline keyboard row index the bot expects
- Track a `buyingRow` state (or per-row disabled state) to prevent double-clicks; show "…" while buying
- Keep existing green highlight (`matchRow` style) on matched cards

### `App.tsx`
- Remove `MatchAlert` import and `<MatchAlert .../>` rendering block
- Remove `match`, `handleApproved`, `handleDenied`, `handleExpired` references
- Add `handleBuyCard` callback that calls `sendPurchase(row_index)`
- Pass `onBuyCard={handleBuyCard}` to `CardGrid`

### `useSocket.ts`
- Remove `match` state, `resetMatch`
- Remove event listeners: `match_found`, `match_rejected`, `purchase_approved`, `purchase_denied`, `match_expired`
- Add `sendPurchase(row_index: number)` — emits `purchase_card { row_index }` via `socketRef`
- Return `sendPurchase` from the hook instead of `resetMatch`

### `client.ts`
- Remove `approveMatch()`, `denyMatch()` functions
- Remove `MatchData` interface
- Keep `apiClient` and other functions unchanged

## Backend Changes

### `websocket.py`
- Remove `on_match_found` handler and `emit("match_found", ...)` call
- Remove `emit("purchase_approved", ...)` and `emit("purchase_denied", ...)` in routes
- Add `on_purchase_card` listener: receives `{ row_index }` from frontend, relays to scraper
- Remove pending match re-send logic from `on_connect`
- Remove Discord notification trigger (was in `on_match_found`)
- Remove `_match_to_dict` helper function (no longer needed)

### `store.py`
- Remove `ActiveMatch` dataclass
- Remove all match methods: `set_match`, `get_match`, `approve_match`, `deny_match`, `clear_match`, `has_pending`
- Keep: card list storage, scrape count, target amount, scraper state

### `routes.py`
- Remove `POST /api/approve` endpoint
- Remove `POST /api/deny` endpoint
- Remove `has_pending_match` and `active_match` from `GET /api/status` response
- Remove `_match_to_dict` import from websocket
- Keep: `GET /api/status`, `POST /api/target_amount`, `GET /api/scraper/status`, `GET /api/debug/store`

### `app.py`
- Remove `MatchTimer` import and instantiation
- Remove `on_match_expire` callback function
- Remove `_match_to_dict` import from websocket
- Update `create_app` return tuple to exclude `timer`
- No structural changes otherwise — the new `purchase_card` event is registered via `register_socketio_events`

### `timer.py`
- Remove entire file — match expiration monitoring is no longer needed

### `run.py`
- Remove `timer` from the `create_app` return tuple unpacking
- Remove `timer.stop()` from the shutdown handler

## Scraper Changes

### `main.py`
- Remove the `for match in matches:` loop body that pauses refresher, waits for approval, and calls `purchaser.purchase()`
- `on_refresh_text` now only: parses all cards, emits metrics, logs detected matches
- Register `purchase_card` handler via `ws_client.set_purchase_handler()` that:
  1. Receives `{ row_index }`
  2. Calls `purchaser.purchase()` — needs a `GiftCardMatch` reconstructed from the latest cards data
  3. Goes back to listings after purchase

### `ws_client.py`
- Remove `wait_for_approval()`, `_approval_event`, `_denial_event`, `_approved`
- Remove `emit_match()`
- Remove `on_purchase_approved` and `on_purchase_denied` handlers
- Add `set_purchase_handler(handler: Callable[[int], None])` — registers callback for incoming `purchase_card` events

### `purchaser.py`
- No changes — `purchase(match: GiftCardMatch)` is called from the new handler path

### `bot_client.py`
- No changes — `click_purchase()` and `go_back_to_listings()` reused as-is

### `refresher.py`
- No changes — `pause()`/`resume()` still exist for manual controls but are no longer called automatically during match handling

## Error Handling

- **Frontend**: If the WebSocket is disconnected, `sendPurchase` logs a warning and does nothing. The Buy button remains enabled so the user can retry.
- **Backend**: If the scraper is disconnected when `purchase_card` arrives, the backend logs a warning. The event is not queued — the user must retry.
- **Scraper**: If purchase fails (e.g., bot navigation error), the scraper logs the error and attempts to return to listings. Polling resumes regardless.
- **Double-buy prevention**: Frontend disables the Buy button for that row after click. Since cards refresh on each poll cycle, the button state resets naturally.

## What Stays the Same

- Card parsing, matching, and display in CardGrid
- Manual pause/resume/restart controls in StatusPanel
- Target amount settings
- Log stream
- Scraper polling and refresh cycle
- Filter verification
- Scraper state tracking
