# Buy Flow with Registration Display — Design Spec

## Overview

When a card matches the target amount, the scraper auto-verifies it to determine registration status. The frontend displays this status (🟢 Unregistered / 🔴 Registered / ⚪ Unknown) alongside each card. All matched cards show a Buy button. Clicking Buy initiates a two-step purchase flow: the scraper opens the card detail screen, the frontend shows a confirmation modal with the card details, and the user clicks Confirm or Cancel.

## Architecture

```
┌──────────┐    initiate_purchase    ┌──────────┐    initiate_purchase    ┌──────────┐
│ Frontend │ ──────────────────────► │ Backend  │ ──────────────────────► │ Scraper  │
│          │                         │          │                         │          │
│          │ ◄──── card_status ───── │ ◄─────── │ ◄── auto-verify cards   │          │
│          │ ◄── purchase_preview ── │ ◄─────── │ ◄── read detail screen  │          │
│          │                         │          │                         │          │
│          │ ─── confirm_purchase ──► │ ───────► │ ─────► ✅ Confirm       │          │
│          │ ─── cancel_purchase ───► │ ───────► │ ─────► ❌ Cancel        │          │
│          │ ◄── purchase_complete ─ │ ◄─────── │ ◄──── result            │          │
└──────────┘                         └──────────┘                         └──────────┘
```

## Auto-Verification (Enhanced)

On each refresh, for **every amount match** (not just unregistered):
1. Scraper pauses refresher
2. Clicks Purchase on the card
3. Reads full card details from the detail screen (ID, BIN, balance, price, registration status)
4. Clicks Cancel to return to listings
5. Emits `card_status` event to frontend
6. Resumes refresher

This replaces the current `verified_match` event with a richer `card_status` event that includes full details and status for ALL matches.

### card_status Payload

```json
{
  "card_number": 3,
  "status": "unregistered",
  "id": "1125704",
  "bin": "420495xx",
  "balance": 2.63,
  "price": 1.03,
  "currency": "USD",
  "rate": 39,
  "raw_text": "💳 Card Details..."
}
```

Status values:
- `"unregistered"` — card shows "⚪ Unregistered"
- `"registered"` — card shows "🔴 Registered" or "🟡 Used in Google"
- `"unknown"` — could not determine status from text

## Buy Flow (Two-Step)

### Step 1 — Initiate Purchase

- User clicks **Buy** button on any matched card (regardless of registration status)
- Frontend emits `initiate_purchase` to backend → scraper
- Scraper pauses refresher
- Scraper clicks **Purchase** on Telegram
- Detail screen appears
- Scraper reads full card details from the detail screen
- Scraper emits `purchase_preview` to frontend with the card details

### Step 2 — Confirm or Cancel

Frontend displays a purchase confirmation modal showing:
- Card ID, BIN, balance, price
- Registration status (🟢 / 🔴 / ⚪)
- **Confirm Purchase** button
- **Cancel** button

**Confirm:**
- Frontend emits `confirm_purchase` to backend → scraper
- Scraper clicks **✅ Confirm** on Telegram
- Purchase completes
- Scraper emits `purchase_complete` `{card_number, success: true}`
- Scraper returns to listings, resumes refresher

**Cancel:**
- Frontend emits `cancel_purchase` to backend → scraper
- Scraper clicks **❌ Cancel** on Telegram
- Scraper returns to listings, resumes refresher
- Scraper emits `purchase_complete` `{card_number, success: false, reason: "user_cancelled"}`

## Frontend Display

### CardGrid Row

Each matched card row shows:
- Card number, BIN, amount, discount
- Registration status badge: 🟢 Unregistered / 🔴 Registered / ⚪ Unknown
- **Buy** button (available on all matches)

### Purchase Modal

Appears when `purchase_preview` is received:
- Card details from the preview
- Confirm / Cancel buttons
- Disappears on `purchase_complete`

## Events

| Event | Direction | Payload | Purpose |
|-------|-----------|---------|---------|
| `card_status` | Scraper → Frontend | `{card_number, status, id, bin, balance, price, currency, rate, raw_text}` | Auto-verification result per match |
| `initiate_purchase` | Frontend → Scraper | `{card_number, button_row}` | User wants to buy this card |
| `purchase_preview` | Scraper → Frontend | `{card_number, id, bin, balance, price, currency, rate, status, raw_text}` | Card details for confirmation modal |
| `confirm_purchase` | Frontend → Scraper | `{card_number, button_row}` | User confirmed purchase |
| `cancel_purchase` | Frontend → Scraper | `{card_number}` | User cancelled purchase |
| `purchase_complete` | Scraper → Frontend | `{card_number, success, reason?}` | Purchase finished |

## Scraper Changes

### bot_client.py
- Add `read_card_details(bot_entity)` — reads the detail screen text and extracts ID, BIN, balance, price, rate, registration status
- Update `check_registration()` to use `read_card_details()` and return a dict instead of bool
- Add `click_confirm(bot_entity)` — clicks the ✅ Confirm button
- Keep `click_cancel(bot_entity)` as-is

### ws_client.py
- Add `emit_card_status(card_data)` — replaces `emit_verified_match`
- Add `emit_purchase_preview(card_data)`
- Add `emit_purchase_complete(result)`
- Add handlers for `initiate_purchase`, `confirm_purchase`, `cancel_purchase`

### main.py
- Replace verification block in `on_refresh_text` to emit `card_status` for ALL matches (not just unregistered)
- Remove `verified_match` emission
- Add `on_initiate_purchase()` handler: click Purchase, read details, emit `purchase_preview`
- Add `on_confirm_purchase()` handler: click Confirm, emit `purchase_complete`
- Add `on_cancel_purchase()` handler: click Cancel, emit `purchase_complete`

## Backend Changes

### websocket.py
- Replace `verified_match` handler with `card_status` handler (relay to all clients)
- Add `initiate_purchase` handler (relay to scraper)
- Add `purchase_preview` handler (relay to all clients)
- Add `confirm_purchase` handler (relay to scraper)
- Add `cancel_purchase` handler (relay to scraper)
- Add `purchase_complete` handler (relay to all clients)

## Frontend Changes

### useSocket.ts
- Replace `verifiedCards` state with `cardStatuses` state: `Map<number, CardStatus>`
- Replace `verified_match` listener with `card_status` listener
- Add `purchasePreview` state and `purchaseComplete` state
- Add listeners for `purchase_preview`, `purchase_complete`
- Add `initiatePurchase()`, `confirmPurchase()`, `cancelPurchase()` emitters
- Remove `sendPurchase()` (replaced by new flow)

### CardGrid.tsx
- Add `cardStatuses` prop (Map of card_number → CardStatus)
- Show registration badge on each match row
- Buy button on ALL matches (not just verified)
- Clicking Buy calls `onInitiatePurchase(card)`

### PurchaseModal.tsx (new)
- Displays when `purchasePreview` is set
- Shows card details from preview
- Confirm button → calls `onConfirmPurchase()`
- Cancel button → calls `onCancelPurchase()`
- Closes on `purchaseComplete`

### App.tsx
- Wire new hooks and modal into the layout

## Edge Cases

| Scenario | Handling |
|----------|----------|
| User clicks Buy while another purchase is pending | Queue or ignore — single purchase at a time |
| Card disappears while modal is open | Modal stays open; confirm/cancel will fail gracefully |
| Scraper disconnects during purchase | Frontend times out, shows error |
| Detail screen has no Confirm button (e.g. insufficient balance) | Scraper detects missing Confirm, emits `purchase_complete` with `success: false` |
| User clicks Cancel in modal | Scraper clicks ❌ Cancel on Telegram, resumes |
