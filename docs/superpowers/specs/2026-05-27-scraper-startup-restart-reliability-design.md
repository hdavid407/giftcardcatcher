# Scraper Startup & Restart Reliability

**Date:** 2026-05-27
**Status:** Approved design

## Problem

The scraper process crashes during startup before connecting to the backend, causing two symptoms:

1. **On initial start** — the scraper navigates the bot menus but never enters the poll loop. It exits with "Filter verification failed after N attempts — stopping scraper."
2. **On restart button** — the frontend shows "scraper offline" because the backend's restart command is forwarded via Socket.IO to the scraper, but no scraper process is running to receive it.

## Root Causes

### 1. FilterVerifier regex breaks with multi-word/comma-separated filter text
The regex `Filters:\s*(\S+)` captures the first non-whitespace token after "Filters:". If the bot outputs `Filters: GiftCardMall, Amazon`, the capture is `GiftCardMall,` (with trailing comma). The `.strip("`'\"")` call doesn't strip commas, so `"GiftCardMall," != "GiftCardMall"` and verification fails.

### 2. "Back to Listings" fallback undoes the filter selection
After clicking the GiftCardMall filter button, the code polls for a Refresh button (5 attempts × 1s). If it doesn't appear, it tries clicking "Back to Listings" / "Back" — which likely cancels the filter and returns to the unfiltered listings. Navigation returns `True` (Refresh button visible in unfiltered view), but the GiftCardMall filter is no longer active. The subsequent `verify_filter()` test refresh fails because the filter line doesn't match.

### 3. `restart()` skips filter re-verification
The `BotClient.restart()` method navigates back to listings but never re-verifies that the filter was actually applied. The scraper's `do_restart()` callback emits `"running"` state immediately after navigation returns True, even if the filter is missing.

### 4. Frontend restart button has no effect on crashed scraper
The restart flow is: Frontend → Socket.IO → Backend → Socket.IO → Scraper. If the scraper process has exited, the Socket.IO room has no recipient, and the backend logs "No scraper connected — cannot forward control."

## Design

### A. Fix identified bugs in scraper

#### A1. Fix FilterVerifier regex
**File:** `scraper/filter_verifier.py`
**Change:** Replace `r"Filters:\s*(\S+)"` with `r"Filters:\s*([\w]+)"`. The `\w` character class matches only word characters (letters, digits, underscore), naturally stripping trailing commas, periods, and other punctuation.

#### A2. Remove "Back to Listings" fallback, increase poll timeout
**File:** `scraper/bot_client.py` — `navigate_to_listings()`
**Changes:**
- Remove the "Back to Listings" / "Back" fallback section after the initial poll loop
- Increase the post-filter poll from 5s to 15s (the bot may take time to switch views)
- If the poll still doesn't find Refresh, go directly to the `/start` → Listing fallback (which resets to a known state)

#### A3. Add filter re-verification to `restart()`
**File:** `scraper/bot_client.py` — `restart()`
**Change:** After `navigate_to_listings()`, call `verify_filter()`. Return `False` if verification fails.

**File:** `scraper/main.py` — `do_restart()` callback
**Change:** Require `bot_client.restart()` to return True (navigation + filter verification passed) before emitting `"running"` state.

### B. Better debugging on verification failure

#### B1. Log actual bot message on filter mismatch
**File:** `scraper/filter_verifier.py` — `is_correct_filter()`
**Change:** When the filter doesn't match, log the expected filter, the extracted filter, and the first 500 characters of the raw message text. This lets you see exactly what the bot returned so you can adjust the regex or expected filter name.

#### B2. Verification bypass already exists
`FILTER_VERIFICATION_ENABLED` is already wired in `.env` and `ScraperConfig`. No changes needed.

### C. Process-level restart from frontend

#### C1. Add ScraperProcessManager to backend
**New file:** `backend/process_manager.py`
Manages the scraper as a subprocess of the backend:

- `start()` — launches `python -m scraper.main` as a subprocess from the project root directory, inheriting environment variables (for .env loading)
- `stop()` — sends SIGINT to the subprocess, waits up to 10s, kills if necessary
- `restart()` — stop + start
- Logs scraper stdout/stderr via the backend logger
- Exposes `is_running` property

#### C2. Integrate into backend startup
**File:** `backend/run.py`
On backend startup, auto-start the scraper subprocess.

#### C3. Wire restart button to process manager
**File:** `backend/websocket.py`
When `scraper_control: restart` is received and no scraper SID is registered, call `ScraperProcessManager.restart()` instead of logging an error. Emit `scraper_state: starting` to the frontend immediately, and `scraper_state: running` once the new scraper connects.

**File:** `backend/store.py` or `backend/app.py`
The process manager instance is passed through the app factory so websocket handlers can access it.

### Files Changed

| File | Change |
|------|--------|
| `scraper/filter_verifier.py` | Fix regex, add debug logging |
| `scraper/bot_client.py` | Fix navigation fallback, fix restart() |
| `scraper/main.py` | Fix do_restart() handler |
| `backend/process_manager.py` | New file — scraper subprocess manager |
| `backend/run.py` | Auto-start scraper subprocess |
| `backend/app.py` | Pass process manager through factory |
| `backend/websocket.py` | Wire restart to process manager |

### Testing

1. **Unit tests** — `FilterVerifier` regex with comma-separated and backtick-wrapped filters
2. **Manual test** — Start backend, verify scraper subprocess starts and connects
3. **Manual test** — Kill scraper process, click frontend restart, verify it relaunches
4. **Manual test** — Set `FILTER_VERIFICATION_ENABLED=false`, verify scraper starts and enters poll loop without verification
