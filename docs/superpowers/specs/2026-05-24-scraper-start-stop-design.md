# Scraper Start/Stop/Restart Controls — Design Spec

## Overview

Add pause/resume and restart controls to the frontend dashboard, allowing the user to temporarily stop the scraper's refresh loop or fully restart the scraper process (reconnecting to Telegram and re-navigating to listings) without touching the terminal.

## Architecture

The control flow is a simple command-reply pattern over the existing Socket.IO connection:

```
Frontend ──scraper_control──► Backend ──forward──► Scraper
   ▲                              │
   └────scraper_state (broadcast)◄┘
```

### Events

| Event | Direction | Payload | Purpose |
|-------|-----------|---------|---------|
| `scraper_control` | Frontend → Backend | `{ action: "pause" \| "resume" \| "restart" }` | User initiates a control action |
| `scraper_control` | Backend → Scraper | `{ action: "pause" \| "resume" \| "restart" }` | Backend relays command to scraper |
| `scraper_state` | Scraper → Backend | `{ state: "running" \| "paused" \| "restarting" \| "error", last_refresh?: string }` | Scraper reports its current state |
| `scraper_state` | Backend → All clients | `{ state, last_refresh?, reason? }` | Backend broadcasts state to all frontends |

The backend acts as a thin relay. The scraper is the source of truth for its own state.

## Scraper Changes

### 1. Refresher — add user pause/resume

- Add `_user_paused` flag (default `False`)
- When `_user_paused` is `True`, `refresh_once()` returns `None` immediately without clicking Refresh
- `poll_loop()` continues running — it just does nothing on each iteration while paused
- Add `pause_user()` / `resume_user()` methods to toggle the flag
- `pause()` / `resume()` remain for match-timeout pauses (orthogonal to user pause)
- Add `is_user_paused` property for state queries

### 2. BotClient — add `restart()` method

- Disconnect Telethon client (`await client.disconnect()`)
- Re-create client with same session file
- `await client.start()` → re-authenticate
- Re-navigate to GiftCardMall listings via `navigate_to_listings()`
- Return success/failure

### 3. ScraperWSClient — add control event listener

- Listen for `scraper_control` from backend
- Dispatch to `Refresher` (pause/resume) or `BotClient` (restart)
- After any state change, emit `scraper_state` back to backend

## Backend Changes

### 1. New Socket.IO handler: `scraper_control` (from frontend)

- Receives `{ action }` from frontend
- Forwards to scraper client via `emit("scraper_control", ...)`
- If scraper is offline, immediately reply with `scraper_state: { state: "error", reason: "scraper offline" }`

### 2. New Socket.IO handler: `scraper_state` (from scraper)

- Receives state updates from scraper
- Stores in `MatchStore` for REST API access
- Broadcasts to all frontend clients via `emit("scraper_state", ..., broadcast=True)`

### 3. REST endpoint: `GET /api/scraper/status`

- Returns current scraper state for page-load scenarios (before Socket.IO connects)
- Response: `{ state: string, last_refresh?: string, reason?: string }`

## Frontend Changes

### 1. useSocket.ts — add scraper state

- New state: `scraperState: "running" | "paused" | "restarting" | "error"`
- Listen for `scraper_state` events and update state
- Emit `scraper_control` via callback: `sendControl(action)`

### 2. StatusPanel.tsx — add control buttons

- Add a row below the metrics with two buttons:
  - **⏸️ Pause / ▶️ Resume** — toggles based on current state
  - **🔄 Restart** — always available, disabled while `restarting`
- Show spinner/loading state while `restarting`
- Show error badge if state is `error`

### 3. Visual placement

- Buttons sit right below the scrape count / card count / target amount row
- Compact horizontal layout to avoid clutter

## Error Handling

| Scenario | Behavior |
|---|---|
| Scraper offline when control sent | Backend replies immediately with `error` state; frontend shows "Scraper offline" |
| Restart fails mid-navigation | Scraper emits `error` state with reason; stays in error until manual restart |
| Pause during pending match | Pause is deferred until match resolves (or match timeout), then pauses |
| Multiple frontends send conflicting commands | Last command wins; scraper state is broadcast after each change |

## Testing

1. **Pause test**: Click Pause → scraper stops clicking Refresh → status shows "Paused" → cards stop updating
2. **Resume test**: Click Resume → scraper resumes Refresh → status shows "Running"
3. **Restart test**: Click Restart → status shows "Restarting" → scraper disconnects/reconnects → status shows "Running"
4. **Offline test**: Stop scraper process → click Pause → frontend shows "Scraper offline"
