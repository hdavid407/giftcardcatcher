# Frontend Dashboard Enhancement — Design Document

**Date:** 2026-05-24  
**Status:** Approved  
**Goal:** Enhance the React Expo frontend with real-time scrape metrics, a live card grid, and adjustable target amount controls.

---

## 1. Overview

Three new features for the existing dashboard:
1. **Scrape Counter** — live total of refresh cycles performed
2. **Live Card Grid** — real-time display of all cards from the latest bot refresh
3. **Adjustable Target Amount** — user can change the dollar amount the scraper watches for, without restarting

---

## 2. Architecture

```
Scraper ──(Socket.IO)──► Backend ──(Socket.IO)──► Frontend
   │                        │                        │
   ├─ cards_update          ├─ broadcast             ├─ render CardGrid
   ├─ scrape_count          ├─ broadcast             ├─ update counter
   └─ match_found           └─ broadcast             └─ highlight matches

Frontend ──(REST POST)──► Backend ──(Socket.IO)──► Scraper
   │                        │                        │
   └─ /api/target_amount    └─ emit target_changed   └─ update matcher
```

---

## 3. Components

### 3.1 Scraper Changes (`scraper/`)

| File | Change |
|------|--------|
| `matcher.py` | Add `set_target_amount()` method; make `target_amount` mutable |
| `refresher.py` | Emit `scrape_count` after each refresh; emit `cards_update` with parsed card list |
| `ws_client.py` | Listen for `target_amount_changed` event from backend |
| `main.py` | Wire new events; update matcher when target amount changes |

**Card parsing:** Extract all card rows from bot message text into structured objects:
```python
{
  "card_number": 1,
  "bin": "420495xx",
  "amount": 940.52,
  "currency": "USD",
  "discount": 39,
  "button_row": 2,
  "is_match": false
}
```

### 3.2 Backend Changes (`backend/`)

| File | Change |
|------|--------|
| `store.py` | Add `scrape_count`, `latest_cards`, `target_amount` fields |
| `websocket.py` | Handle `cards_update`, `scrape_count` from scraper; emit `target_amount_changed` to scraper |
| `routes.py` | Add `POST /api/target_amount` endpoint |

### 3.3 Frontend Changes (`frontend/`)

| File | Change |
|------|--------|
| `hooks/useSocket.ts` | Listen for `cards_update`, `scrape_count`; expose `setTargetAmount` function |
| `components/StatusPanel.tsx` | Add scrape counter display |
| `components/CardGrid.tsx` | New component: scrollable grid of all cards, highlights matches |
| `components/SettingsPanel.tsx` | New component: target amount input with save button |
| `App.tsx` | Compose new components; add settings toggle |

---

## 4. Data Flow

### 4.1 Normal Refresh
1. Scraper clicks Refresh, gets updated message
2. Scraper parses all cards into structured list
3. Scraper emits `cards_update` + `scrape_count` to backend
4. Backend stores data, broadcasts to all frontend clients
5. Frontend updates card grid and counter

### 4.2 Match Detection
1. Scraper checks each card against current `target_amount`
2. If match found, proceeds to registration check (existing flow)
3. Matching cards are flagged `is_match: true` in `cards_update`
4. Frontend highlights matching rows in the grid

### 4.3 Target Amount Change
1. User enters new amount in frontend settings
2. Frontend POSTs `/api/target_amount` with new value
3. Backend updates stored target, emits `target_amount_changed`
4. Scraper receives event, calls `matcher.set_target_amount()`
5. Next refresh uses new amount

---

## 5. UI Design

### Card Grid
- Table-like layout: Card # | BIN | Amount | Discount | Status
- Match rows: green left border, bold amount
- Scrollable within fixed-height container
- Shows "Last updated: 11:42:03" timestamp

### Settings Panel
- Collapsible section (gear icon toggle)
- Number input: "Target Amount ($)" — default 50
- Save button → shows "Saved ✓" confirmation
- Current target displayed in header subtitle

### Status Panel Enhancement
- Add: "Total Scrapes: 47" below connection status
- Add: "Cards on page: 10" from latest refresh

---

## 6. API Changes

### Socket.IO Events (Scraper → Backend → Frontend)

| Event | Direction | Payload |
|-------|-----------|---------|
| `cards_update` | scraper → backend → frontend | `{ cards: [...], timestamp }` |
| `scrape_count` | scraper → backend → frontend | `{ count: 47 }` |
| `target_amount_changed` | backend → scraper | `{ amount: 50.0 }` |

### REST Endpoint

```
POST /api/target_amount
Body: { "amount": 50.0 }
Headers: X-API-Key
```

---

## 7. Error Handling

| Scenario | Handling |
|----------|----------|
| Scraper disconnects mid-refresh | Frontend shows stale data with "Last updated: X min ago" warning |
| Target amount is invalid (negative, non-numeric) | Frontend validates; backend rejects with 400 |
| Card parsing fails on unexpected format | Scraper logs error, emits empty cards list, continues |
| Large card list (60+ items) | Frontend uses FlatList with virtualization for performance |

---

## 8. Testing

- **Unit:** Card parsing with sample bot message texts
- **Integration:** Change target amount via REST, verify scraper matcher updates
- **E2E:** Frontend renders card grid, counter increments, match highlights correctly

---

## 9. Approval

- Design: ✅ Approved
- This spec: Pending user review
