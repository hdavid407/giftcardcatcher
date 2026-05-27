# Auto-Buy Mode Design

## Overview

A dashboard toggle that enables automatic purchase of unregistered gift cards matching the target amount. When auto-buy is ON, the scraper will verify a card's registration status and immediately purchase it if unregistered — no manual confirmation required. After purchase (success or failure), auto-buy automatically turns OFF and sends a Discord notification.

## Goals

- Eliminate manual clicks for buying unregistered cards
- Prevent accidental multiple purchases (auto-buy disables after one attempt)
- Notify user via Discord with purchase result
- Keep frontend simple: one toggle switch

## Non-Goals

- Buying multiple cards in sequence (one-shot only)
- Conditional auto-buy based on price/rate thresholds
- Automatic retry on failed purchases

## Architecture

```
[Frontend Toggle] ──toggle_auto_buy──► [Backend Relay] ──toggle_auto_buy──► [Scraper State]
                                                                             │
                                                    (verification finds unregistered card)
                                                                             │
                                                                             ▼
                                                    [Scraper: click Confirm, wait for result]
                                                                             │
                                        ┌────────────────────────────────────┴────────────────────────────────────┐
                                        │                                                                         │
                                        ▼                                                                         ▼
                                [Purchase Success]                                                      [Purchase Failure]
                                - Set auto-buy OFF                                                      - Set auto-buy OFF
                                - Discord: "✅ Bought..."                                               - Discord: "❌ Failed..."
                                - Emit purchase_complete                                                - Emit purchase_complete
                                - Emit auto_buy_status                                                  - Emit auto_buy_status
```

## State Management

### Scraper-side State (source of truth)

- `_auto_buy_enabled: bool = False` — stored in `scraper/main.py`
- Persists across refreshes
- Not affected by frontend disconnections

### Frontend State (replica)

- `autoBuyEnabled: boolean` — stored in `useSocket.ts`
- Updated via `auto_buy_status` events from scraper
- UI toggle emits `toggle_auto_buy` to request state change

## Data Flow

### 1. Enabling Auto-Buy

1. User clicks toggle ON in frontend
2. Frontend emits `toggle_auto_buy: { enabled: true }`
3. Backend relays to scraper
4. Scraper sets `_auto_buy_enabled = True`
5. Scraper emits `auto_buy_status: { enabled: true }` to all connected frontends
6. Frontend updates toggle to ON

### 2. Disabling Auto-Buy (Manual)

1. User clicks toggle OFF in frontend
2. Frontend emits `toggle_auto_buy: { enabled: false }`
3. Backend relays to scraper
4. Scraper sets `_auto_buy_enabled = False`
5. Scraper emits `auto_buy_status: { enabled: false }`

### 3. Auto-Buy Trigger (Verification → Purchase)

1. Scraper finds matching card during refresh
2. Scraper clicks Purchase button to check registration
3. `read_card_details()` returns status
4. **If status == "unregistered" AND `_auto_buy_enabled == True`:**
   - Do NOT click Cancel
   - Call `click_confirm()` to purchase
   - Poll for purchase result (reuse `handle_confirm_purchase` logic)
   - Set `_auto_buy_enabled = False`
   - Send Discord notification
   - Emit `purchase_complete`
   - Emit `auto_buy_status: { enabled: false, reason: "purchase_completed" }`
5. **If status != "unregistered" OR auto-buy is OFF:**
   - Click Cancel (normal verification flow)
   - Auto-buy state unchanged

### 4. Auto-Disable After Purchase

Regardless of success or failure, auto-buy is turned off after the purchase attempt completes. This prevents:
- Accidentally buying the next matching card
- Spending more than intended
- Running out of balance on multiple purchases

## Components

### Frontend

#### New: `AutoBuyToggle.tsx`
- Toggle switch component
- Shows "🤖 Auto-Buy" label
- Visual state: ON (green) / OFF (gray)
- Emits `toggle_auto_buy` on change
- Shows last auto-buy result if available

#### Modified: `useSocket.ts`
- Add `autoBuyEnabled` state
- Add `toggleAutoBuy(enabled: boolean)` function
- Listen for `auto_buy_status` events
- Listen for `auto_buy_result` events (optional, for displaying result)

#### Modified: `App.tsx`
- Import and render `<AutoBuyToggle />`
- Place next to Pause/Restart controls in status area

### Backend

#### Modified: `websocket.py`
- Add handler `toggle_auto_buy` → relay to scraper
- Add broadcast `auto_buy_status` → all frontends
- Store auto-buy state in `MatchStore`

#### Modified: `store.py`
- Add `auto_buy_enabled` field
- Add getter/setter methods

### Scraper

#### Modified: `scraper/main.py`
- Add `_auto_buy_enabled: bool = False`
- Add `handle_toggle_auto_buy(enabled: bool)` handler
- Add `run_auto_buy_purchase(bot, match, details)` function
- Modify verification flow in `on_refresh_text`:
  - After reading card details, check auto-buy + status
  - If auto-buy + unregistered: call `run_auto_buy_purchase`
  - Else: normal Cancel flow
- Ensure auto-buy is disabled on purchase completion (success or failure)

#### Modified: `scraper/ws_client.py`
- Add `emit_auto_buy_status(data)` method
- Add handler registration for `toggle_auto_buy`

#### Modified: `scraper/discord_notifier.py` (or backend)
- Add `notify_auto_buy_complete(card_data, success, result_text)`
- Format: success = "✅ Auto-buy successful! Card ID: {id}, BIN: {bin}, Balance: ${balance}"
- Format: failure = "❌ Auto-buy failed: {reason}"

## Socket.IO Events

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `toggle_auto_buy` | Frontend → Backend → Scraper | `{ enabled: boolean }` | User toggles auto-buy |
| `auto_buy_status` | Scraper → Backend → Frontend | `{ enabled: boolean, reason?: string }` | State change broadcast |
| `purchase_complete` | Scraper → Backend → Frontend | (existing) | Purchase result |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Auto-buy Confirm click fails | Turn off auto-buy, Discord notify failure, emit `purchase_complete` with `reason: "confirm_click_failed"` |
| Purchase result times out | Turn off auto-buy, Discord notify timeout, emit failure |
| Discord webhook fails | Log error, continue with purchase flow |
| Card is registered/unknown | Click Cancel, auto-buy stays ON, normal verification continues |
| Frontend disconnects during auto-buy | Scraper continues, completes purchase, turns off auto-buy |
| User toggles OFF during purchase | Scraper ignores, completes current purchase, then stays OFF |

## Edge Cases

1. **Multiple unregistered cards in same refresh:** Buys the first one, turns off. Remaining cards verified normally.
2. **Auto-buy ON but no unregistered cards found:** Auto-buy stays ON until a match is found.
3. **Auto-buy ON but user manually clicks Buy:** Manual purchase takes priority (sets `_pending_purchase_row`). Verification skips as existing logic handles.
4. **Scraper restarts while auto-buy ON:** State resets to OFF (no persistence needed — user can re-enable).

## Success Criteria

- [ ] Toggle appears on frontend and controls scraper state
- [ ] When auto-buy ON, unregistered cards are purchased without manual confirmation
- [ ] After purchase, auto-buy turns OFF automatically
- [ ] Discord notification sent with purchase result
- [ ] Registered/unknown cards do not trigger auto-buy
- [ ] Manual Buy/Confirm flow still works when auto-buy is OFF
- [ ] Manual Buy/Confirm flow still works when auto-buy is ON (precedence given to manual)
