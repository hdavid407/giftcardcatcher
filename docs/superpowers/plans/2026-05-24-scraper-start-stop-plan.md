# Scraper Start/Stop/Restart Controls — Implementation Plan

## Goal

Implement pause/resume and restart controls for the scraper, accessible from the frontend dashboard via Socket.IO.

## Plan Overview

| Phase | Task | Files | Est. Time |
|-------|------|-------|-----------|
| 1 | Scraper: Add user pause/resume to Refresher | `scraper/refresher.py` | 15 min |
| 2 | Scraper: Add restart to BotClient | `scraper/bot_client.py` | 20 min |
| 3 | Scraper: Wire control events in main + ws_client | `scraper/ws_client.py`, `scraper/main.py` | 25 min |
| 4 | Backend: Add scraper state to store | `backend/store.py` | 10 min |
| 5 | Backend: Add Socket.IO handlers + REST endpoint | `backend/websocket.py`, `backend/routes.py` | 20 min |
| 6 | Frontend: Add scraper state to useSocket | `frontend/hooks/useSocket.ts` | 15 min |
| 7 | Frontend: Add control buttons to StatusPanel | `frontend/components/StatusPanel.tsx` | 20 min |
| 8 | Integration test + commit | All | 20 min |

---

## Phase 1: Scraper — Add User Pause/Resume to Refresher

**File:** `scraper/refresher.py`

1. Add `_user_paused: bool = False` to `__init__`
2. Add `pause_user()` method — sets `_user_paused = True`, logs
3. Add `resume_user()` method — sets `_user_paused = False`, logs
4. Add `is_user_paused` property
5. Modify `refresh_once()` — if `_user_paused`, return `None` immediately (skip the refresh)
6. Keep `poll_loop()` running — it just does nothing while paused

**Validation:** Run scraper, verify it still refreshes normally.

---

## Phase 2: Scraper — Add Restart to BotClient

**File:** `scraper/bot_client.py`

1. Add `restart()` method:
   - `await self._client.disconnect()`
   - Re-create `TelegramClient` with same session file
   - `await self._client.start(phone=self.config.phone)`
   - Get bot entity
   - Call `navigate_to_listings(bot_entity)`
   - Return `True` on success, `False` on failure
2. Add `is_connected` property (check `self._client.is_connected()`)

**Validation:** Manual test — call restart, verify re-navigation works.

---

## Phase 3: Scraper — Wire Control Events

**Files:** `scraper/ws_client.py`, `scraper/main.py`

### ws_client.py:
1. Add `set_control_handler(handler)` — registers callback for `scraper_control` events
2. In `_register_handlers()`, add listener for `scraper_control`:
   - Parse `{ action: "pause" | "resume" | "restart" }`
   - Call registered handler

### main.py:
1. After `ws_client.connect()`, call `ws_client.set_control_handler(on_control)`
2. Implement `on_control(action)`:
   - `"pause"` → `refresher.pause_user()`, emit state `{ state: "paused" }`
   - `"resume"` → `refresher.resume_user()`, emit state `{ state: "running" }`
   - `"restart"` → emit `{ state: "restarting" }`, call `bot_client.restart()`, then emit `{ state: "running" }` or `{ state: "error", reason: ... }`
3. Add periodic state emission (every 30s or on every refresh) so new frontends learn current state

**Validation:** Start scraper, use a test script to emit `scraper_control` events via Socket.IO.

---

## Phase 4: Backend — Add Scraper State to Store

**File:** `backend/store.py`

1. Add `scraper_state` field to `MatchStore` (default: `{ state: "unknown" }`)
2. Add `set_scraper_state(state_dict)` method
3. Add `get_scraper_state()` method

**Validation:** Unit test — set and get state.

---

## Phase 5: Backend — Socket.IO Handlers + REST Endpoint

**Files:** `backend/websocket.py`, `backend/routes.py`

### websocket.py:
1. Add `scraper_control` handler (from frontend):
   - Receives `{ action }`
   - Forward to scraper via `emit("scraper_control", ...)` to the scraper's SID
   - If no scraper connected, emit `scraper_state` with `{ state: "error", reason: "scraper offline" }` to the requesting client
2. Add `scraper_state` handler (from scraper):
   - Call `store.set_scraper_state(data)`
   - Broadcast to all clients via `emit("scraper_state", data, broadcast=True)`
3. Track scraper SID separately from frontend SIDs (use `_detect_client` or a new `X-Client-Type` header)

### routes.py:
1. Add `GET /api/scraper/status`:
   - Return `store.get_scraper_state()` or `{ state: "unknown" }`

**Validation:** Test with curl and a Socket.IO test client.

---

## Phase 6: Frontend — Add Scraper State to useSocket

**File:** `frontend/hooks/useSocket.ts`

1. Add `scraperState` state (type: `"running" | "paused" | "restarting" | "error" | "unknown"`)
2. Listen for `scraper_state` events — update `scraperState`
3. Add `sendControl(action)` callback:
   - `socket.emit("scraper_control", { action })`
4. On initial connect, optionally fetch `GET /api/scraper/status` as fallback

**Validation:** Verify state updates in React DevTools or console logs.

---

## Phase 7: Frontend — Add Control Buttons to StatusPanel

**File:** `frontend/components/StatusPanel.tsx`

1. Add props: `scraperState`, `onPause`, `onResume`, `onRestart`
2. Add button row below metrics:
   - If `scraperState === "running"`: show **⏸️ Pause** button (calls `onPause`)
   - If `scraperState === "paused"`: show **▶️ Resume** button (calls `onResume`)
   - If `scraperState === "restarting"`: show spinner + "Restarting..."
   - If `scraperState === "error"`: show error badge + **🔄 Restart** button
   - Always show **🔄 Restart** button (disabled while `restarting`)
3. Style: compact horizontal row, same dark theme as rest of dashboard

**Validation:** Click buttons, verify scraper responds correctly.

---

## Phase 8: Integration Test + Commit

1. Kill any running scraper/backend processes
2. Start backend: `python -m backend.run`
3. Start scraper: `python -m scraper.main`
4. Open frontend in browser
5. Test sequence:
   - Click **Pause** → verify scraper stops refreshing
   - Click **Resume** → verify scraper resumes
   - Click **Restart** → verify scraper disconnects, reconnects, re-navigates
   - Kill scraper → click **Pause** → verify "Scraper offline" message
6. Fix any issues
7. Commit all changes

---

## Rollback Plan

If any phase introduces bugs:
- Phases 1-3: Scraper-only changes — can be reverted by restoring `scraper/` from git
- Phases 4-5: Backend-only changes — can be reverted by restoring `backend/` from git
- Phases 6-7: Frontend-only changes — can be reverted by restoring `frontend/` from git
- Each phase is independent enough to be rolled back separately

## Dependencies

- Phase 1 must complete before Phase 3
- Phase 2 must complete before Phase 3
- Phase 4 must complete before Phase 5
- Phase 5 must complete before Phase 8
- Phase 6 must complete before Phase 7
- Phase 7 must complete before Phase 8
