# Telegram Gift Card Scraper — Design Document

**Date:** 2026-05-20  
**Status:** Approved  
**Goal:** Automatically monitor a Telegram bot for $50 unregistered GiftCardMall gift cards, alert the user in real time, and allow one-tap approval to purchase before cards sell out (~3 minutes).

---

## 1. Overview

A three-layer system:
1. **Telegram Scraper** (Python + Telethon) — impersonates the user's Telegram account, polls the target bot by pressing Refresh, parses gift card listings, and executes purchases on approval.
2. **Flask Backend** — REST API + WebSocket (Socket.IO) hub. Receives matches from the scraper, broadcasts alerts to the frontend, and forwards user approval/denial back to the scraper.
3. **React Expo Web Frontend** — deployed to Vercel. Real-time dashboard showing monitoring status, live logs, and a prominent match alert with Buy/Skip buttons and a countdown timer.

**Data flow:** Scraper → Flask WebSocket → React app → Flask REST → Scraper clicks Purchase.

---

## 2. Architecture

```
                         Socket.IO (bidirectional)
┌─────────────────┐◄──────────────────────────────────────►┌─────────────────┐
│  Python Scraper │                                         │  Flask Backend  │
│  (Telethon)     │─────(match_found via Socket.IO)───────►│  (Socket.IO)    │
└─────────────────┘◄────(purchase_approved via Socket.IO)──┘
       │  ▲                                                       │  ▲
       │  │                                                       │  │ WebSocket
  (Refresh/                                                    (REST + WS)
  Purchase)                                                         │
       │                                                            ▼
       ▼                                                   ┌─────────────────┐
┌─────────────────┐                                         │  React Expo Web │
│  Telegram Bot   │                                         │  (Vercel)       │
│  (Seller)       │                                         └─────────────────┘
└─────────────────┘
```

---

## 3. Components

### 3.1 Telegram Scraper (`scraper/`)

| File | Purpose |
|------|---------|
| `bot_client.py` | Telethon session manager. Logs in as the user, persists session file, handles reconnection. |
| `refresher.py` | Core polling loop. Sends the Refresh inline keyboard callback, waits for bot response, extracts the updated message with the gift card grid. |
| `matcher.py` | Parses each row of the inline keyboard. Regex matcher looks for `$50` + `unregistered` + `giftcardmall` (case-insensitive). Returns matching row indices and card details. |
| `purchaser.py` | Receives an approved match, sends the corresponding Purchase inline keyboard callback for that specific row. |
| `ws_client.py` | Socket.IO client that connects to Flask backend. Pushes `match_found` events and listens for `purchase_approved` / `purchase_denied` events. |
| `main.py` | Entry point. Orchestrates the loop: refresh → parse → match → notify → (wait for approval) → purchase. |

**Polling strategy:** Refresh every 5 seconds. If a match is found, pause further refreshes until the match is approved, denied, or expires (3-minute countdown). Log every refresh result for transparency.

**Session persistence:** Telethon `.session` file stored locally so re-runs don't require re-authentication.

### 3.2 Flask Backend (`backend/`)

| File | Purpose |
|------|---------|
| `app.py` | Flask app factory with Flask-SocketIO, CORS enabled for Vercel domain. |
| `routes.py` | REST endpoints for frontend: `GET /api/status`, `POST /api/approve`, `POST /api/deny`. |
| `websocket.py` | Socket.IO event handlers. Receives `match_found` from scraper, emits `match_found` / `purchase_confirmed` / `purchase_denied` / `status_update` to frontend. |
| `config.py` | Loads env vars: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TARGET_BOT_USERNAME`, `POLL_INTERVAL`, `FLASK_SECRET_KEY`. |

**State management:** In-memory store for active match + countdown timer. No database needed for MVP.

**Security:** Backend should run on a private server or behind a firewall. The REST API is not publicly exposed without authentication (API key header check).

### 3.3 React Expo Web Frontend (`frontend/`)

| File | Purpose |
|------|---------|
| `App.tsx` | Main layout. Status indicator, live log stream, match alert modal overlay. |
| `components/MatchAlert.tsx` | Prominent alert card when a match is found. Shows card details, **Buy** / **Skip** buttons, and a countdown timer (3 minutes). Plays a sound or vibrates on mobile. |
| `components/StatusPanel.tsx` | Shows scraper connection status, last refresh timestamp, total cards seen this session, current polling interval. |
| `components/LogStream.tsx` | Scrollable live feed of scraper activity (refresh attempts, cards seen, match events). |
| `hooks/useSocket.ts` | Socket.IO client hook. Connects to Flask backend, listens for events, auto-reconnects. |
| `api/client.ts` | Axios wrapper for REST calls to Flask backend. Includes API key header. |

**Deployment:** Built as a web app with Expo and deployed to Vercel. Socket.IO client connects to the Flask backend via WebSocket.

---

## 4. Data Flow

### 4.1 Normal Polling (No Match)
1. Scraper sends Refresh callback to target bot.
2. Bot replies with updated gift card grid.
3. Scraper parses grid, finds no match.
4. Scraper logs result, waits 5 seconds, repeats.

### 4.2 Match Found
1. Scraper parses grid, finds `$50 unregistered giftcardmall` at row N.
2. Scraper emits `match_found` via Socket.IO to Flask backend.
3. Flask stores match in memory, starts 3-minute countdown.
4. Flask emits `match_found` via Socket.IO to all connected clients.
5. React frontend displays `MatchAlert` with card details and countdown.
6. Scraper pauses further refreshes until match is resolved.

### 4.3 User Approves Purchase
1. User taps **Buy** in React frontend.
2. Frontend POSTs `/api/approve` with match ID.
3. Flask emits `purchase_approved` event via Socket.IO.
4. Scraper, connected to Flask as a Socket.IO client, receives the `purchase_approved` event.
5. Scraper sends Purchase callback for row N to target bot.
6. Bot confirms purchase. Scraper logs result, resumes normal polling.

### 4.4 User Denies or Timeout
1. User taps **Skip**, or 3-minute countdown expires.
2. Flask clears active match, emits `purchase_denied` or `match_expired`.
3. Scraper resumes normal polling.

---

## 5. Error Handling

| Scenario | Handling |
|----------|----------|
| Telegram API disconnect | Telethon auto-reconnect with exponential backoff. Log and emit `status_update`. |
| Target bot doesn't respond | Timeout after 10 seconds. Log failure, retry next cycle. |
| Flask backend unreachable | Scraper queues match locally, retries POST with backoff. Frontend shows "Backend disconnected" warning. |
| Purchase callback fails | Log error, emit `purchase_failed`, allow user to retry manually. |
| Multiple matches in one refresh | Alert for all matches simultaneously. User can approve one or more. |
| Match expires during approval | Frontend disables Buy button, shows "Expired". Scraper resumes polling. |

---

## 6. Configuration & Secrets

All secrets loaded from environment variables:
- `TELEGRAM_API_ID` — from my.telegram.org
- `TELEGRAM_API_HASH` — from my.telegram.org
- `TELEGRAM_PHONE` — user's phone number for Telethon login
- `TARGET_BOT_USERNAME` — e.g., `@giftcardsellerbot`
- `REFRESH_BUTTON_TEXT` — text of the refresh button (default: "Refresh")
- `PURCHASE_BUTTON_TEXT` — text of the purchase button (default: "Purchase")
- `POLL_INTERVAL_SECONDS` — default 5
- `MATCH_TIMEOUT_SECONDS` — default 180 (3 minutes)
- `FLASK_SECRET_KEY` — for session/security
- `API_KEY` — shared secret between frontend and backend
- `BACKEND_URL` — Flask server URL for frontend

---

## 7. Testing Strategy

- **Unit tests** for `matcher.py` with sample message texts.
- **Integration test** for `refresher.py` using a mock Telegram bot (Telethon test server or recorded sessions).
- **End-to-end test** — run scraper + Flask locally, simulate a match via mock POST, verify frontend alert renders and approval flows through.

---

## 8. Future Enhancements (Out of Scope)

- Multiple gift card criteria (not just $50 GCM).
- Purchase history log with SQLite/PostgreSQL.
- Telegram bot notifications as a fallback alert channel.
- Auto-purchase mode (no human approval) with configurable confidence threshold.
- Multi-account scraping for higher refresh rates.

---

## 9. Open Questions / Risks

1. **Telegram rate limits:** Aggressive polling (every 5s) may trigger flood limits. If hit, Telethon will auto-backoff. We may need to adjust interval dynamically.
2. **Bot UI changes:** If the seller changes button text or layout, the scraper will break. We'll make button text configurable.
3. **Session security:** The `.session` file grants full account access. It must be stored securely and never committed.
4. **Vercel + WebSocket:** Vercel serverless functions don't support persistent WebSocket connections. The frontend will use Socket.IO with `transports: ['websocket', 'polling']` fallback, but the Flask backend must run on a persistent server (not serverless).

---

## 10. Approval

- Architecture: ✅ Approved
- Components: ✅ Approved
- This spec: Pending user review
