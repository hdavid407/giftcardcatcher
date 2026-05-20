# Telegram Gift Card Scraper — Implementation Plan

**Date:** 2026-05-20  
**Design Spec:** `docs/superpowers/specs/2026-05-20-telegram-giftcard-scraper-design.md`

---

## Phase 1: Project Scaffolding & Environment

**Goal:** Set up the monorepo structure, Python environment, and dependency files.

| # | Task | Files / Commands | Notes |
|---|------|------------------|-------|
| 1.1 | Create root `README.md` with setup instructions | `README.md` | |
| 1.2 | Create root `.gitignore` (Python, Node, secrets) | `.gitignore` | Exclude `.env`, `*.session`, `node_modules/`, `__pycache__/` |
| 1.3 | Create root `requirements.txt` for Python deps | `requirements.txt` | `telethon`, `flask`, `flask-socketio`, `python-socketio`, `python-dotenv`, `requests`, `eventlet` |
| 1.4 | Create scraper package structure | `scraper/__init__.py` | |
| 1.5 | Create backend package structure | `backend/__init__.py` | |
| 1.6 | Create frontend Expo project | `frontend/` | `npx create-expo-app frontend --template blank` then configure for web |
| 1.7 | Create root `.env.example` template | `.env.example` | All required env vars documented |

**Checkpoint:** Directory structure exists, no code yet, dependencies installable.

---

## Phase 2: Telegram Scraper Core (Python)

**Goal:** Build the Telethon-based scraper that can log in, refresh, parse, and match.

| # | Task | Files | Notes |
|---|------|-------|-------|
| 2.1 | Implement `bot_client.py` — Telethon session manager | `scraper/bot_client.py` | Handles auth, session persistence, reconnection |
| 2.2 | Implement `refresher.py` — polling loop | `scraper/refresher.py` | Sends Refresh callback, captures bot response message |
| 2.3 | Implement `matcher.py` — gift card parser + matcher | `scraper/matcher.py` | Regex for `$50` + `unregistered` + `giftcardmall`. Returns list of matches with row index, card text, price |
| 2.4 | Implement `purchaser.py` — purchase execution | `scraper/purchaser.py` | Sends Purchase callback for a given row index |
| 2.5 | Implement `ws_client.py` — Socket.IO client to Flask | `scraper/ws_client.py` | Emits `match_found`, listens for `purchase_approved` / `purchase_denied` |
| 2.6 | Implement `main.py` — orchestrator | `scraper/main.py` | Loop: connect → refresh → match → (if match) emit → wait for approval/deny/timeout → purchase or resume |
| 2.7 | Add `scraper/config.py` — env var loader | `scraper/config.py` | Wraps python-dotenv, validates required vars |

**Checkpoint:** Can run `python -m scraper.main` and it logs in, refreshes the bot, prints parsed cards, and indicates whether a match was found. No backend connection yet.

---

## Phase 3: Flask Backend

**Goal:** Build the Socket.IO + REST hub that connects scraper and frontend.

| # | Task | Files | Notes |
|---|------|-------|-------|
| 3.1 | Implement `backend/config.py` — env var loader | `backend/config.py` | `FLASK_SECRET_KEY`, `API_KEY`, `CORS_ORIGINS` |
| 3.2 | Implement `backend/app.py` — Flask-SocketIO app factory | `backend/app.py` | CORS, SocketIO init, register routes & events |
| 3.3 | Implement `backend/websocket.py` — Socket.IO events | `backend/websocket.py` | `on_match_found` (from scraper), `on_connect`/`on_disconnect` (from frontend) |
| 3.4 | Implement `backend/routes.py` — REST endpoints | `backend/routes.py` | `GET /api/status`, `POST /api/approve`, `POST /api/deny`. API key auth via header. |
| 3.5 | Implement in-memory match store | `backend/store.py` | Active match + countdown timer state. Thread-safe. |
| 3.6 | Add countdown timer logic | `backend/timer.py` | Emits `match_expired` if no action within 180s. Cleans up state. |
| 3.7 | Create `backend/run.py` entry point | `backend/run.py` | `socketio.run(app, host='0.0.0.0', port=5000)` |

**Checkpoint:** Can run `python backend/run.py`, connect a test Socket.IO client, emit `match_found`, and see it broadcast. REST endpoints return expected responses.

---

## Phase 4: React Expo Web Frontend

**Goal:** Build the real-time dashboard deployed to Vercel.

| # | Task | Files | Notes |
|---|------|-------|-------|
| 4.1 | Set up Expo web configuration | `frontend/app.json`, `frontend/package.json` | Ensure `"web"` bundler configured |
| 4.2 | Install frontend deps | `frontend/package.json` | `socket.io-client`, `axios`, `@expo/vector-icons` |
| 4.3 | Implement `api/client.ts` — Axios wrapper | `frontend/api/client.ts` | Base URL from env, API key header |
| 4.4 | Implement `hooks/useSocket.ts` — Socket.IO hook | `frontend/hooks/useSocket.ts` | Auto-connect, listen for events, expose `emit` |
| 4.5 | Implement `components/StatusPanel.tsx` | `frontend/components/StatusPanel.tsx` | Connection status, last refresh, cards seen |
| 4.6 | Implement `components/LogStream.tsx` | `frontend/components/LogStream.tsx` | Scrollable list of log entries |
| 4.7 | Implement `components/MatchAlert.tsx` | `frontend/components/MatchAlert.tsx` | Full-screen overlay on match. Card details, countdown timer, Buy/Skip buttons. Sound/vibrate on match. |
| 4.8 | Implement `App.tsx` — main layout | `frontend/App.tsx` | Compose StatusPanel, LogStream, MatchAlert. Global state via React Context or useReducer. |
| 4.9 | Add environment config for Vercel | `frontend/.env.example` | `EXPO_PUBLIC_BACKEND_URL`, `EXPO_PUBLIC_API_KEY` |

**Checkpoint:** Can run `npx expo start --web` locally, see the dashboard, and test with mock Socket.IO events.

---

## Phase 5: Integration & Wiring

**Goal:** Connect all three layers and verify end-to-end flow.

| # | Task | Files | Notes |
|---|------|-------|-------|
| 5.1 | Wire scraper → backend Socket.IO | `scraper/ws_client.py` | Ensure `match_found` payload reaches Flask and is broadcast |
| 5.2 | Wire backend → frontend Socket.IO | `backend/websocket.py` | Ensure frontend receives `match_found` and renders alert |
| 5.3 | Wire frontend approval → backend REST | `frontend/api/client.ts` + `backend/routes.py` | Buy button POSTs `/api/approve`, backend emits `purchase_approved` |
| 5.4 | Wire backend approval → scraper | `backend/websocket.py` + `scraper/ws_client.py` | Scraper receives `purchase_approved`, triggers `purchaser.py` |
| 5.5 | Handle deny / timeout flow | all | Skip button and timer expiry both clear state and resume polling |
| 5.6 | Add structured logging throughout | all | Consistent log format for LogStream consumption |

**Checkpoint:** Run all three layers locally. Simulate a match by manually triggering `match_found`. Verify alert appears, Buy triggers purchase callback, Skip resumes polling.

---

## Phase 6: Deployment

**Goal:** Get the backend and frontend running in production.

| # | Task | Files / Commands | Notes |
|---|------|------------------|-------|
| 6.1 | Create `vercel.json` for frontend | `frontend/vercel.json` | SPA routing rules |
| 6.2 | Deploy frontend to Vercel | `vercel --prod` | From `frontend/` directory |
| 6.3 | Create backend deployment docs | `docs/deployment.md` | Instructions for running Flask on a VPS, Railway, Render, etc. |
| 6.4 | Add production CORS config | `backend/config.py` | Restrict to Vercel domain |
| 6.5 | Test production end-to-end | — | Verify real-time alerts work across internet |

**Checkpoint:** Frontend live on Vercel, backend running on persistent host, user can receive alerts and approve purchases from their phone.

---

## Phase 7: Hardening & Polish

**Goal:** Make it robust enough for real money transactions.

| # | Task | Files | Notes |
|---|------|-------|-------|
| 7.1 | Add Telegram flood wait handling | `scraper/refresher.py` | Detect `FloodWaitError`, back off dynamically, notify user |
| 7.2 | Add purchase confirmation parsing | `scraper/purchaser.py` | Verify bot response after Purchase callback indicates success |
| 7.3 | Add retry logic for failed purchases | `scraper/purchaser.py` | 1 retry if first attempt fails |
| 7.4 | Add match deduplication | `backend/store.py` | Don't alert twice for the same card within a window |
| 7.5 | Add graceful shutdown | `scraper/main.py`, `backend/run.py` | SIGTERM handler, close sockets cleanly |
| 7.6 | Add sound + vibration on match | `frontend/components/MatchAlert.tsx` | `Audio` API + `Vibration` API |
| 7.7 | Add dark mode support | `frontend/` | Theme toggle |

**Checkpoint:** System handles edge cases gracefully, user trusts it with real purchases.

---

## Task Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 5 ◄──► Phase 3
              │           ▲
              └───────────┘
Phase 4 ───────────────────────────────► Phase 6 ──► Phase 7
```

Phases 2, 3, and 4 can be developed in parallel after Phase 1. Phase 5 requires all three. Phase 6 requires Phase 5. Phase 7 is optional polish.

---

## Estimated Effort

| Phase | Estimated Time |
|-------|-------------|
| 1. Scaffolding | 30 min |
| 2. Scraper Core | 2–3 hours |
| 3. Flask Backend | 1.5–2 hours |
| 4. React Frontend | 2–3 hours |
| 5. Integration | 1–1.5 hours |
| 6. Deployment | 1 hour |
| 7. Hardening | 1–2 hours |
| **Total** | **~10–14 hours** |

---

## Next Step

Ready to begin implementation. Recommend starting with **Phase 1 (Scaffolding)** and then running **Phases 2, 3, and 4 in parallel**.
