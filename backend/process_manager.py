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
                    logger.info(
                        "[scraper] %s",
                        line.decode("utf-8", errors="replace").rstrip(),
                    )
        except Exception:
            pass
