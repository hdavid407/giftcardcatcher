# Scraper Startup & Restart Reliability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the scraper so it reliably starts, navigates, verifies the GiftCardMall filter, and survives restarts — including process-level restart from the frontend when the scraper has crashed.

**Architecture:** Three independent fix groups: (A) bug fixes in scraper's filter verification and navigation logic, (B) better logging on verification failure, (C) a subprocess manager in the backend that launches/restarts the scraper as a child process so the frontend restart button works even after a crash.

**Tech Stack:** Python 3.14, Telethon, Flask/Socket.IO, asyncio, subprocess

---

### Task 1: Fix FilterVerifier regex

**Files:**
- Modify: `scraper/filter_verifier.py:10-11`

- [ ] **Step 1: Change regex to handle commas and punctuation**

```python
# scraper/filter_verifier.py

class FilterVerifier:
    # Changed from \S+ to [\w]+ — only captures word characters,
    # naturally stripping trailing commas, periods, brackets, etc.
    FILTER_PATTERN = re.compile(r"Filters:\s*([\w]+)", re.IGNORECASE)
```

- [ ] **Step 2: Run existing tests**

Run: `cd /home/vscode/projects/telegram-buyer && source .venv/bin/activate && python -m pytest tests/test_filter_verifier.py -v`
Expected: All tests pass (the existing tests should still work with `\w`)

- [ ] **Step 3: Commit**

```bash
git add scraper/filter_verifier.py
git commit -m "fix: use \w+ in FilterVerifier regex to handle comma-separated filters"
```

---

### Task 2: Add debug logging to FilterVerifier

**Files:**
- Modify: `scraper/filter_verifier.py:29-35`

- [ ] **Step 1: Add full message logging on mismatch**

Replace the `logger.warning("Filter mismatch: ...")` section to also log the raw message text:

```python
# scraper/filter_verifier.py — inside is_correct_filter()

        if not result:
            logger.warning(
                "Filter mismatch: expected '%s', got '%s'",
                self.expected_filter,
                actual,
            )
            logger.debug(
                "Filter verification failed. Raw message (first 500 chars):\n%s",
                message_text[:500],
            )
        return result
```

- [ ] **Step 2: Commit**

```bash
git add scraper/filter_verifier.py
git commit -m "feat: log raw message text on filter verification failure"
```

---

### Task 3: Fix navigate_to_listings — remove "Back to Listings" fallback, increase poll timeout

**Files:**
- Modify: `scraper/bot_client.py:188-230` (navigate_to_listings method)

- [ ] **Step 1: Replace the post-filter polling and fallback logic**

Current code (conceptual):
```python
        # Poll for listings screen (Refresh button) with retries
        for attempt in range(5):
            await asyncio.sleep(1.0)
            msg = await self.get_latest_message(bot_entity)
            if self._has_button(msg, self.config.refresh_button_text):
                logger.info("On listings screen after filter selection")
                return True

        # Try Back to Listings
        result = await self.click_button_by_text(
            bot_entity, "Back to Listings", wait=3.0, exact=True
        )
        if result is None:
            result = await self.click_button_by_text(bot_entity, "Back", wait=2.0, exact=True)

        # Final verification
        msg = await self.get_latest_message(bot_entity)
        if self._has_button(msg, self.config.refresh_button_text):
            logger.info("Successfully navigated to GiftCardMall listings")
            return True
```

Replace with:
```python
        # Poll for listings screen (Refresh button) with retries
        # Increased from 5s to 15s — bot may need time to apply filter
        for attempt in range(15):
            await asyncio.sleep(1.0)
            msg = await self.get_latest_message(bot_entity)
            if self._has_button(msg, self.config.refresh_button_text):
                logger.info("On listings screen after filter selection (attempt %d)", attempt + 1)
                return True

        # Do NOT try "Back to Listings" / "Back" — that may cancel the filter.
        # Go straight to the /start → Listing fallback to reset to known state.
        logger.warning("Refresh button not found after 15s — falling back to /start → Listing")
        await self._client.send_message(bot_entity, "/start")
        await asyncio.sleep(3.0)
        result = await self.click_button_by_text(
            bot_entity, self.config.listings_button_text, wait=3.0, exact=True
        )
        if result is None:
            logger.error("Fallback: Could not find Listings button after /start")
            return False

        msg = await self.get_latest_message(bot_entity)
        if self._has_button(msg, self.config.refresh_button_text):
            logger.info("Successfully navigated to GiftCardMall listings via fallback")
            return True

        logger.error("Navigation failed — Refresh button not found")
        return False
```

- [ ] **Step 2: Commit**

```bash
git add scraper/bot_client.py
git commit -m "fix: remove 'Back to Listings' fallback that cancels filter, increase poll to 15s"
```

---

### Task 4: Fix restart() to verify filter after navigation

**Files:**
- Modify: `scraper/bot_client.py:63-78` (restart method)

- [ ] **Step 1: Add filter verification to restart()**

Current code:
```python
    async def restart(self) -> bool:
        try:
            logger.info("Restarting Telegram client...")
            await self.stop()
            await asyncio.sleep(1.0)
            await self.start()
            bot_entity = await self.get_bot_entity()
            nav_ok = await self.navigate_to_listings(bot_entity)
            if nav_ok:
                logger.info("Telegram client restarted and navigated successfully")
                return True
            else:
                logger.error("Restarted but navigation to listings failed")
                return False
        except Exception as e:
            logger.error("Failed to restart Telegram client: %s", e)
            return False
```

Replace with:
```python
    async def restart(self) -> bool:
        try:
            logger.info("Restarting Telegram client...")
            await self.stop()
            await asyncio.sleep(1.0)
            await self.start()
            bot_entity = await self.get_bot_entity()
            nav_ok = await self.navigate_to_listings(bot_entity)
            if not nav_ok:
                logger.error("Restarted but navigation to listings failed")
                return False

            # Also verify the GiftCardMall filter is active
            if self.config.filter_verification_enabled:
                filter_ok = await self.verify_filter(bot_entity)
                if not filter_ok:
                    logger.error("Restarted but filter verification failed")
                    return False

            logger.info("Telegram client restarted, navigated, and filter verified")
            return True
        except Exception as e:
            logger.error("Failed to restart Telegram client: %s", e)
            return False
```

- [ ] **Step 2: Commit**

```bash
git add scraper/bot_client.py
git commit -m "fix: verify filter after restart navigation"
```

---

### Task 5: Fix do_restart() handler in main.py to check restart result

**Files:**
- Modify: `scraper/main.py:111-121` (do_restart callback)

- [ ] **Step 1: Update the restart handler to check full result**

Current code:
```python
            async def do_restart():
                ok = await bot_client.restart()
                if ws_client._connected:
                    if ok:
                        await ws_client.emit_scraper_state({"state": "running"})
                    else:
                        await ws_client.emit_scraper_state({"state": "error", "reason": "restart failed"})
```

Replace with:
```python
            async def do_restart():
                ok = await bot_client.restart()
                if ws_client._connected:
                    if ok:
                        await ws_client.emit_scraper_state({"state": "running"})
                    else:
                        await ws_client.emit_scraper_state({"state": "error", "reason": "restart failed"})
                else:
                    logger.warning("Backend not connected after restart — state not emitted")
```

(No functional change — the existing code already handles this. Adding a warning log for the disconnected case for visibility.)

- [ ] **Step 2: Commit**

```bash
git add scraper/main.py
git commit -m "chore: add warning log when restart succeeds but backend disconnected"
```

---

### Task 6: Create ScraperProcessManager

**Files:**
- Create: `backend/process_manager.py`

- [ ] **Step 1: Write the process manager**

```python
"""Manages the scraper as a subprocess of the backend."""

import asyncio
import logging
import os
import signal
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


class ScraperProcessManager:
    """Launches, monitors, and restarts the scraper as a child process.

    The scraper runs ``python -m scraper.main`` from the project root
    directory.  The manager captures its stdout/stderr and forwards them
    to the Python logger at INFO level.

    Usage::

        manager = ScraperProcessManager(project_root="/home/.../telegram-buyer")
        manager.start()
        manager.restart()   # stop + start
        manager.stop()
    """

    def __init__(self, project_root: str):
        self._project_root = project_root
        self._process: Optional[subprocess.Popen] = None
        self._python_exe: str = self._resolve_python()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Return True if the scraper subprocess is currently running."""
        return self._process is not None and self._process.poll() is None

    def start(self):
        """Launch the scraper as a subprocess.

        If the scraper is already running this is a no-op.
        """
        if self.is_running:
            logger.info("Scraper already running (pid=%d)", self._process.pid)
            return

        logger.info("Starting scraper subprocess...")
        try:
            self._process = subprocess.Popen(
                [self._python_exe, "-m", "scraper.main"],
                cwd=self._project_root,
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            logger.info("Scraper subprocess started (pid=%d)", self._process.pid)

            # Start a background reader task to log scraper output
            asyncio.create_task(self._reader())
        except Exception as e:
            logger.error("Failed to start scraper subprocess: %s", e)
            self._process = None

    def stop(self):
        """Stop the scraper subprocess gracefully (SIGINT), kill after 10 s."""
        if not self.is_running:
            return

        logger.info("Stopping scraper subprocess (pid=%d)...", self._process.pid)
        try:
            self._process.send_signal(signal.SIGINT)
            self._process.wait(timeout=10)
            logger.info("Scraper subprocess stopped")
        except subprocess.TimeoutExpired:
            logger.warning("Scraper did not exit in 10 s — killing")
            self._process.kill()
            self._process.wait()
        except Exception as e:
            logger.error("Error stopping scraper: %s", e)
        finally:
            self._process = None

    def restart(self):
        """Stop the current scraper (if any) and start a fresh one."""
        logger.info("Restarting scraper subprocess...")
        self.stop()
        self.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_python(self) -> str:
        """Return the path to the Python executable in the venv."""
        # Look for a .venv next to the project root
        venv_python = os.path.join(self._project_root, ".venv", "bin", "python")
        if os.path.exists(venv_python):
            return venv_python
        # Fall back to sys.executable
        return sys.executable

    async def _reader(self):
        """Continuously read scraper subprocess stdout and log it."""
        try:
            while self._process is not None and self._process.poll() is None:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self._process.stdout.readline
                )
                if line:
                    logger.info("[scraper] %s", line.decode("utf-8", errors="replace").rstrip())
        except Exception:
            pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/process_manager.py
git commit -m "feat: add ScraperProcessManager for subprocess lifecycle"
```

---

### Task 7: Integrate process manager into backend startup

**Files:**
- Modify: `backend/app.py` (pass process_manager through factory)
- Modify: `backend/run.py` (auto-start scraper on backend boot)

- [ ] **Step 1: Update create_app to accept and return a process_manager**

In `backend/app.py`:

```python
# At the top, add import
from .process_manager import ScraperProcessManager

# In create_app's signature and return type
def create_app(config: BackendConfig) -> tuple[Flask, SocketIO, MatchStore, MatchTimer, ScraperProcessManager]:
    """
    Create and configure the Flask application.

    Returns:
        (app, socketio, store, timer, process_manager) tuple
    """
    # ... existing code ...

    # Scraper subprocess manager
    # project_root is the parent of backend/
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    process_manager = ScraperProcessManager(project_root)

    # ... existing code ...

    return app, socketio, store, timer, process_manager
```

- [ ] **Step 2: Wire the return value in run.py**

In `backend/run.py`:

```python
def main():
    logger.info("Starting Flask backend server")

    config = BackendConfig()
    app, socketio, store, timer, process_manager = create_app(config)

    # Auto-start the scraper subprocess on backend boot
    process_manager.start()

    logger.info("Listening on %s:%d", config.host, config.port)

    try:
        socketio.run(
            app,
            host=config.host,
            port=config.port,
            debug=False,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        timer.stop()
        process_manager.stop()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app.py backend/run.py
git commit -m "feat: integrate ScraperProcessManager into backend lifecycle"
```

---

### Task 8: Wire restart button to process manager in websocket.py

**Files:**
- Modify: `backend/websocket.py` (use process_manager when scraper SID is missing)

- [ ] **Step 1: Pass process_manager to register_socketio_events**

In `backend/app.py`, update the call to pass process_manager:

```python
    # Register routes and events
    register_routes(app, store, socketio, config)
    register_socketio_events(socketio, store, config, process_manager)
```

In `backend/websocket.py`, update the function signature:

```python
def register_socketio_events(
    socketio: SocketIO,
    store: MatchStore,
    config: BackendConfig,
    process_manager: "ScraperProcessManager",  # forward reference, avoid circular import
):
```

- [ ] **Step 2: Replace the "No scraper connected" warning with a restart**

In the `on_scraper_control` handler in `backend/websocket.py`:

```python
    @socketio.on("scraper_control")
    def on_scraper_control(data: dict):
        """Forward control commands from frontend to scraper."""
        action = data.get("action", "")
        logger.info("Scraper control received: %s", action)
        if _scraper_sid:
            emit("scraper_control", data, room=_scraper_sid)
        elif action == "restart":
            logger.info("No scraper connected — restarting via process manager")
            emit("scraper_state", {"state": "starting"})
            process_manager.restart()
        else:
            logger.warning("No scraper connected — cannot forward control")
            emit("scraper_state", {"state": "error", "reason": "scraper offline"})
```

- [ ] **Step 3: Commit**

```bash
git add backend/app.py backend/websocket.py
git commit -m "feat: wire frontend restart button to ScraperProcessManager when scraper disconnected"
```

---

### Task 9: Verification

- [ ] **Step 1: Run unit tests**

Run: `cd /home/vscode/projects/telegram-buyer && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass (especially `test_filter_verifier.py`)

- [ ] **Step 2: Restart the backend**

```bash
# Kill existing backend, then restart
cd /home/vscode/projects/telegram-buyer && source .venv/bin/activate && python -m backend.run
```

Expected: Backend starts, scraper subprocess auto-launches. Logs show:
- `[backend.process_manager] INFO: Starting scraper subprocess...`
- `[backend.process_manager] INFO: Scraper subprocess started (pid=...)`
- Scraper connects to backend via Socket.IO

- [ ] **Step 3: Test frontend restart button**

Open http://localhost:8081, click the restart button (🔄).

Expected: If the scraper is running, it restarts (reconnects Telegram, re-navigates). If not running, the process manager launches a new one. Frontend shows "running" state after success.

- [ ] **Step 4: Test crash recovery**

Kill the scraper subprocess manually:
```bash
kill <scraper-pid>
```

Then click restart in the frontend. Expected: Process manager starts a new scraper, it connects, frontend shows "running".
