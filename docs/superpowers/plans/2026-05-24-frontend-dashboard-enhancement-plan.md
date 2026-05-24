# Frontend Dashboard Enhancement — Implementation Plan

**Date:** 2026-05-24  
**Design Spec:** `docs/superpowers/specs/2026-05-24-frontend-dashboard-enhancement-design.md`

---

## Phase 1: Scraper — Card Parsing & Events

| # | Task | Files | Notes |
|---|------|-------|-------|
| 1.1 | Add `set_target_amount()` to `matcher.py` | `scraper/matcher.py` | Make `target_amount` mutable via method |
| 1.2 | Add `parse_all_cards()` to `matcher.py` | `scraper/matcher.py` | Return structured list of all cards from message text |
| 1.3 | Emit `cards_update` + `scrape_count` from `refresher.py` | `scraper/refresher.py` | After each refresh, emit parsed cards and increment counter |
| 1.4 | Listen for `target_amount_changed` in `ws_client.py` | `scraper/ws_client.py` | New event handler that updates matcher |
| 1.5 | Wire new events in `main.py` | `scraper/main.py` | Pass cards to ws_client; handle target amount change |

**Checkpoint:** Scraper emits cards_update and scrape_count after each refresh; responds to target amount changes.

---

## Phase 2: Backend — Store & Broadcast

| # | Task | Files | Notes |
|---|------|-------|-------|
| 2.1 | Extend `store.py` with scrape metrics | `backend/store.py` | Add `scrape_count`, `latest_cards`, `target_amount` |
| 2.2 | Handle `cards_update` + `scrape_count` in `websocket.py` | `backend/websocket.py` | Store and broadcast to all clients |
| 2.3 | Handle `target_amount_changed` emission in `websocket.py` | `backend/websocket.py` | Emit to scraper when REST endpoint is hit |
| 2.4 | Add `POST /api/target_amount` to `routes.py` | `backend/routes.py` | Validate, update store, emit event |

**Checkpoint:** Backend receives and broadcasts all new events; REST endpoint works.

---

## Phase 3: Frontend — New Components

| # | Task | Files | Notes |
|---|------|-------|-------|
| 3.1 | Update `useSocket.ts` with new events | `frontend/hooks/useSocket.ts` | Listen for `cards_update`, `scrape_count`; add `setTargetAmount` function |
| 3.2 | Update `StatusPanel.tsx` with scrape counter | `frontend/components/StatusPanel.tsx` | Show total scrapes and card count |
| 3.3 | Create `CardGrid.tsx` | `frontend/components/CardGrid.tsx` | Scrollable grid/table of all cards, highlight matches |
| 3.4 | Create `SettingsPanel.tsx` | `frontend/components/SettingsPanel.tsx` | Target amount input with save button |
| 3.5 | Update `App.tsx` layout | `frontend/App.tsx` | Compose CardGrid, SettingsPanel; add settings toggle |

**Checkpoint:** Frontend renders card grid, shows scrape count, can change target amount.

---

## Phase 4: Integration & Testing

| # | Task | Notes |
|---|------|-------|
| 4.1 | Wire scraper → backend → frontend card flow | Verify cards appear in grid after refresh |
| 4.2 | Wire target amount change end-to-end | Change in frontend → scraper updates → next refresh uses new amount |
| 4.3 | Test match highlighting | Set target to existing amount, verify green highlight |
| 4.4 | Test scrape counter | Verify counter increments with each refresh |

**Checkpoint:** All features work together; no regressions in existing match/purchase flow.

---

## Task Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 4
              │
Phase 3 ──────┘
```

Phases 1 and 3 can be developed in parallel. Phase 4 requires both.

---

## Estimated Effort

| Phase | Estimated Time |
|-------|-------------|
| 1. Scraper | 1 hour |
| 2. Backend | 45 min |
| 3. Frontend | 1.5 hours |
| 4. Integration | 30 min |
| **Total** | **~4 hours** |

---

## Next Step

Ready to begin implementation. Recommend starting with **Phase 1 (Scraper)** and **Phase 3 (Frontend)** in parallel.
