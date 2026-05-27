# Remove Match Popup — Replace with Inline Buy Buttons — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the modal "Buy Now / Skip" popup with inline Buy buttons on matched cards in the card grid, using direct WebSocket `purchase_card` commands.

**Architecture:** Remove the match/approve/deny state machine from backend and scraper. Replace it with a simple WebSocket relay: frontend emits `purchase_card { row_index }` → backend relays to scraper → scraper buys immediately. Polling continues uninterrupted.

**Tech Stack:** TypeScript (React Native/Expo frontend), Python (Flask/Socket.IO backend, Telethon scraper)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/store.py` | Modify | Remove match state machine, keep card/scrape/target/scraper state |
| `backend/timer.py` | Delete | Match expiration monitor — no longer needed |
| `backend/routes.py` | Modify | Remove approve/deny endpoints, remove match from status |
| `backend/websocket.py` | Modify | Remove match events, add `purchase_card` relay to scraper |
| `backend/app.py` | Modify | Remove match timer and `_match_to_dict` import |
| `backend/run.py` | Modify | Remove timer from tuple unpacking and shutdown |
| `frontend/components/MatchAlert.tsx` | Delete | Modal popup — replaced by inline button |
| `frontend/api/client.ts` | Modify | Remove `MatchData`, `approveMatch`, `denyMatch` |
| `frontend/hooks/useSocket.ts` | Modify | Remove match state/events, add `sendPurchase` |
| `frontend/components/CardGrid.tsx` | Modify | Add Buy button on matched rows |
| `frontend/App.tsx` | Modify | Remove MatchAlert rendering, wire `handleBuyCard` |
| `scraper/ws_client.py` | Modify | Remove approval events/wait, add `purchase_card` handler |
| `scraper/main.py` | Modify | Remove approval loop, register purchase handler |

---

### Task 1: Remove match state machine from backend store

**Files:**
- Modify: `backend/store.py` (full file)

- [ ] **Step 1: Remove `ActiveMatch` dataclass and all match methods from store.py**

Remove the `ActiveMatch` dataclass (lines 10–26) and all match-related methods: `set_match`, `get_match`, `approve_match`, `deny_match`, `clear_match`, `has_pending`. Also remove the `_active` and `_last_match_id` fields from `__init__`.

```python
"""In-memory match store. Thread-safe via a lock."""

import threading
from typing import Optional


class MatchStore:
    """Thread-safe in-memory store for cards, metrics, and scraper state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._scrape_count: int = 0
        self._latest_cards: list[dict] = []
        self._target_amount: float = 50.0
        self._scraper_state: dict = {"state": "unknown"}

    # --- Card / metrics methods ---

    def get_scrape_count(self) -> int:
        """Get the total number of scrapes performed."""
        with self._lock:
            return self._scrape_count

    def increment_scrape_count(self) -> int:
        """Increment the scrape count. Returns the new count."""
        with self._lock:
            self._scrape_count += 1
            return self._scrape_count

    def set_latest_cards(self, cards: list[dict]):
        """Store the latest parsed cards."""
        with self._lock:
            self._latest_cards = cards

    def get_latest_cards(self) -> list[dict]:
        """Get the latest parsed cards."""
        with self._lock:
            return list(self._latest_cards)

    def set_target_amount(self, amount: float):
        """Update the target amount."""
        with self._lock:
            self._target_amount = amount

    def get_target_amount(self) -> float:
        """Get the current target amount."""
        with self._lock:
            return self._target_amount

    def set_scraper_state(self, state: str, reason: str = None):
        """Update the scraper state."""
        with self._lock:
            self._scraper_state = {"state": state}
            if reason:
                self._scraper_state["reason"] = reason

    def get_scraper_state(self) -> dict:
        """Get the current scraper state."""
        with self._lock:
            return dict(self._scraper_state)
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from backend.store import MatchStore; s = MatchStore(); print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/store.py
git commit -m "refactor: remove match state machine from MatchStore"
```

---

### Task 2: Delete match timer

**Files:**
- Delete: `backend/timer.py`

- [ ] **Step 1: Delete the timer file**

```bash
rm backend/timer.py
```

- [ ] **Step 2: Commit**

```bash
git add backend/timer.py
git commit -m "refactor: remove MatchTimer, no longer needed"
```

---

### Task 3: Remove match routes from backend

**Files:**
- Modify: `backend/routes.py`

- [ ] **Step 1: Remove approve/deny endpoints and match from status**

Replace the file content to remove match-related routes and imports:

```python
"""REST API routes for the Flask backend."""

import logging

from flask import Flask, request
from flask_socketio import SocketIO

from .config import BackendConfig
from .store import MatchStore
from .websocket import _check_api_key

logger = logging.getLogger(__name__)


def register_routes(app: Flask, store: MatchStore, socketio: SocketIO, config: BackendConfig):
    """Register all REST API routes."""

    @app.route("/api/status")
    def get_status():
        """Health check and current state."""
        return {
            "status": "running",
        }

    @app.route("/api/target_amount", methods=["POST"])
    def set_target_amount():
        """Update the target amount the scraper watches for."""
        if not _check_api_key(request, config):
            return {"error": "Unauthorized"}, 401

        data = request.get_json() or {}
        amount = data.get("amount")

        if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
            return {"error": "Invalid amount. Must be a positive number."}, 400

        store.set_target_amount(float(amount))
        logger.info("Target amount updated to %.2f", amount)

        # Notify the scraper
        socketio.emit("target_amount_changed", {"amount": float(amount)})

        return {"status": "updated", "target_amount": float(amount)}

    @app.route("/api/scraper/status")
    def get_scraper_status():
        """Get the current scraper state."""
        return store.get_scraper_state()

    @app.route("/api/debug/store")
    def debug_store():
        """Debug endpoint to inspect the store state."""
        return {
            "scrape_count": store.get_scrape_count(),
            "cards_count": len(store.get_latest_cards()),
            "latest_cards": store.get_latest_cards()[:3],  # first 3
        }
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from backend.routes import register_routes; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/routes.py
git commit -m "refactor: remove approve/deny endpoints and match status from routes"
```

---

### Task 4: Update backend websocket — remove match events, add purchase_card relay

**Files:**
- Modify: `backend/websocket.py`

- [ ] **Step 1: Rewrite websocket.py**

Replace the file to remove all match-related handlers and add the `purchase_card` relay:

```python
"""Socket.IO event handlers for the Flask backend."""

import logging
from typing import Optional

from flask import request
from flask_socketio import SocketIO, emit

from .config import BackendConfig
from .store import MatchStore

logger = logging.getLogger(__name__)

_scraper_sid: Optional[str] = None


def _detect_client(req) -> str:
    """Detect whether the connecting client is the scraper or a frontend."""
    user_agent = req.headers.get("User-Agent", "")
    if "python" in user_agent.lower() or "aiohttp" in user_agent.lower():
        return "scraper"
    return "frontend"


def _check_api_key(req, config: BackendConfig) -> bool:
    """Validate the API key header if required."""
    if not config.api_key:
        return True
    return req.headers.get("X-API-Key") == config.api_key


def register_socketio_events(
    socketio: SocketIO,
    store: MatchStore,
    config: BackendConfig,
    process_manager: "ScraperProcessManager" = None,
):
    """Register all Socket.IO event handlers."""
    from .process_manager import ScraperProcessManager

    @socketio.on("connect")
    def on_connect(auth=None):
        """Handle client connection."""
        client_type = _detect_client(request)
        logger.info(
            "Socket.IO client connected: %s (%s)",
            request.sid,
            client_type,
        )

        nonlocal _scraper_sid
        if client_type == "scraper":
            _scraper_sid = request.sid
            logger.info("Scraper registered with SID: %s", _scraper_sid)

        # Send current scraper state to newly connected client
        state = store.get_scraper_state()
        emit("scraper_state", state)

        # Sync current cards and scrape count to newly connected clients
        latest_cards = store.get_latest_cards()
        if latest_cards:
            emit("cards_update", {"cards": latest_cards, "timestamp": 0})

        scrape_count = store.get_scrape_count()
        if scrape_count > 0:
            emit("scrape_count", {"count": scrape_count})

    @socketio.on("disconnect")
    def on_disconnect():
        logger.info("Socket.IO client disconnected: %s", request.sid)
        nonlocal _scraper_sid
        if request.sid == _scraper_sid:
            _scraper_sid = None
            logger.info("Scraper disconnected")

    @socketio.on("purchase_card")
    def on_purchase_card(data: dict):
        """
        Called when the frontend wants to purchase a specific card.
        Receives: { row_index: int }
        Relays to the scraper process.
        """
        row_index = data.get("row_index")
        if row_index is None:
            logger.warning("purchase_card received without row_index")
            return

        logger.info("Purchase request for row %d", row_index)

        if _scraper_sid:
            emit("purchase_card", {"row_index": row_index}, room=_scraper_sid)
            logger.info("Relayed purchase_card to scraper (row %d)", row_index)
        else:
            logger.warning("Scraper not connected — cannot relay purchase_card")
            emit("purchase_card_error", {
                "row_index": row_index,
                "reason": "Scraper not connected",
            })

    @socketio.on("scraper_state")
    def on_scraper_state(data: dict):
        """Receive scraper state updates and broadcast to frontends."""
        state = data.get("state", "unknown")
        reason = data.get("reason")
        store.set_scraper_state(state, reason)
        emit("scraper_state", data, broadcast=True)

    @socketio.on("status_update")
    def on_status_update(data: dict):
        """Receive status updates from scraper and broadcast."""
        emit("status_update", data, broadcast=True)

    @socketio.on("cards_update")
    def on_cards_update(data: dict):
        """Receive card list from scraper, store it, and broadcast."""
        cards = data.get("cards", [])
        store.set_latest_cards(cards)
        emit("cards_update", data, broadcast=True)

    @socketio.on("scrape_count")
    def on_scrape_count(data: dict):
        """Receive scrape count from scraper and broadcast."""
        emit("scrape_count", data, broadcast=True)

    @socketio.on("target_amount_changed")
    def on_target_amount_changed(data: dict):
        """Relay target amount changes."""
        emit("target_amount_changed", data, broadcast=True)

    @socketio.on("scraper_control")
    def on_scraper_control(data: dict):
        """Relay scraper control commands to the scraper."""
        if _scraper_sid:
            emit("scraper_control", data, room=_scraper_sid)
        else:
            logger.warning("Scraper not connected — cannot relay scraper_control")
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from backend.websocket import register_socketio_events, _check_api_key; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/websocket.py
git commit -m "refactor: remove match events, add purchase_card relay to scraper"
```

---

### Task 5: Update backend app.py and run.py

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/run.py`

- [ ] **Step 1: Update app.py — remove MatchTimer and _match_to_dict**

Replace `backend/app.py`:

```python
"""Flask application factory for the backend."""

import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from .config import BackendConfig
from .process_manager import ScraperProcessManager
from .store import MatchStore
from .routes import register_routes
from .websocket import register_socketio_events

logger = logging.getLogger(__name__)


def create_app(config: BackendConfig) -> tuple[Flask, SocketIO, MatchStore, ScraperProcessManager]:
    """
    Create and configure the Flask application.

    Returns:
        (app, socketio, store, process_manager) tuple
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key

    # CORS
    CORS(app, origins=config.cors_origins)

    # Socket.IO
    socketio = SocketIO(
        app,
        cors_allowed_origins=config.cors_origins,
        async_mode="eventlet",
        logger=logger,
        engineio_logger=False,
    )

    # In-memory store
    store = MatchStore()

    # Scraper subprocess manager
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    process_manager = ScraperProcessManager(project_root)

    # Register routes and events
    register_routes(app, store, socketio, config)
    register_socketio_events(socketio, store, config, process_manager)

    logger.info("Flask app created (CORS origins: %s)", config.cors_origins)

    return app, socketio, store, process_manager
```

- [ ] **Step 2: Update run.py — remove timer references**

Replace `backend/run.py`:

```python
"""Entry point for the Flask backend server."""

import logging
import sys

from .app import create_app
from .config import BackendConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backend.run")


def main():
    logger.info("Starting Flask backend server")

    config = BackendConfig()
    app, socketio, store, process_manager = create_app(config)

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
        process_manager.stop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from backend.app import create_app; print('OK')"`  
Run: `python -c "from backend.run import main; print('OK')"`
Expected: Both print `OK` with no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app.py backend/run.py
git commit -m "refactor: remove MatchTimer from app factory and run entry point"
```

---

### Task 6: Delete MatchAlert component and clean up client.ts

**Files:**
- Delete: `frontend/components/MatchAlert.tsx`
- Modify: `frontend/api/client.ts`

- [ ] **Step 1: Delete MatchAlert.tsx**

```bash
rm frontend/components/MatchAlert.tsx
```

- [ ] **Step 2: Clean up client.ts — remove MatchData, approveMatch, denyMatch**

Replace `frontend/api/client.ts`:

```typescript
import axios from "axios";

const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:5000";
const API_KEY = process.env.EXPO_PUBLIC_API_KEY || "";

const apiClient = axios.create({
  baseURL: BACKEND_URL,
  headers: {
    "Content-Type": "application/json",
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  },
});

export interface StatusResponse {
  status: string;
}

export async function getStatus(): Promise<StatusResponse> {
  const res = await apiClient.get("/api/status");
  return res.data;
}

export default apiClient;
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: No errors related to `client.ts` (there may be pre-existing errors in other files — that's fine).

- [ ] **Step 4: Commit**

```bash
git add frontend/components/MatchAlert.tsx frontend/api/client.ts
git commit -m "refactor: remove MatchAlert component and match API functions"
```

---

### Task 7: Update useSocket hook — remove match, add sendPurchase

**Files:**
- Modify: `frontend/hooks/useSocket.ts`

- [ ] **Step 1: Rewrite useSocket.ts**

Replace `frontend/hooks/useSocket.ts`:

```typescript
import { useEffect, useRef, useState, useCallback } from "react";
import { io, Socket } from "socket.io-client";

const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:5000";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export interface CardInfo {
  card_number: number;
  bin: string;
  amount: number;
  currency: string;
  discount: number | null;
  button_row: number;
  is_match: boolean;
  raw_text: string;
}

export type ScraperState = "running" | "paused" | "restarting" | "error" | "unknown";

interface UseSocketReturn {
  status: ConnectionStatus;
  logs: string[];
  lastRefresh: string | null;
  cards: CardInfo[];
  scrapeCount: number;
  targetAmount: number;
  scraperState: ScraperState;
  sendControl: (action: "pause" | "resume" | "restart") => void;
  sendPurchase: (rowIndex: number) => void;
}

export function useSocket(): UseSocketReturn {
  const socketRef = useRef<Socket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [logs, setLogs] = useState<string[]>([]);
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);
  const [cards, setCards] = useState<CardInfo[]>([]);
  const [scrapeCount, setScrapeCount] = useState<number>(0);
  const [targetAmount, setTargetAmount] = useState<number>(50);
  const [scraperState, setScraperState] = useState<ScraperState>("unknown");

  const addLog = useCallback((msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [`[${timestamp}] ${msg}`, ...prev].slice(0, 200));
  }, []);

  useEffect(() => {
    const socket = io(BACKEND_URL, {
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 2000,
    });

    socketRef.current = socket;

    socket.on("connect", () => {
      setStatus("connected");
      addLog("Connected to backend");
    });

    socket.on("disconnect", () => {
      setStatus("disconnected");
      addLog("Disconnected from backend");
    });

    socket.on("connect_error", () => {
      setStatus("disconnected");
    });

    socket.on("status_update", (data: { last_refresh?: string }) => {
      if (data.last_refresh) {
        setLastRefresh(data.last_refresh);
      }
    });

    socket.on("cards_update", (data: { cards: CardInfo[]; timestamp: number }) => {
      setCards(data.cards);
      addLog(`📋 Cards updated: ${data.cards.length} cards`);
    });

    socket.on("scrape_count", (data: { count: number }) => {
      setScrapeCount(data.count);
    });

    socket.on("target_amount_changed", (data: { amount: number }) => {
      setTargetAmount(data.amount);
      addLog(`🎯 Target amount changed to $${data.amount}`);
    });

    socket.on("scraper_state", (data: { state: ScraperState; reason?: string }) => {
      setScraperState(data.state);
      if (data.reason) {
        addLog(`⚙️ Scraper ${data.state}: ${data.reason}`);
      } else {
        addLog(`⚙️ Scraper state: ${data.state}`);
      }
    });

    socket.on("purchase_card_error", (data: { row_index: number; reason: string }) => {
      addLog(`❌ Purchase failed for row ${data.row_index}: ${data.reason}`);
    });

    return () => {
      socket.disconnect();
    };
  }, [addLog]);

  const sendPurchase = useCallback((rowIndex: number) => {
    if (socketRef.current) {
      socketRef.current.emit("purchase_card", { row_index: rowIndex });
      addLog(`🛒 Purchase requested for row ${rowIndex}`);
    } else {
      addLog("⚠️ Not connected — cannot send purchase request");
    }
  }, [addLog]);

  const sendControl = useCallback((action: "pause" | "resume" | "restart") => {
    if (socketRef.current) {
      socketRef.current.emit("scraper_control", { action });
    }
  }, []);

  return {
    status,
    logs,
    lastRefresh,
    cards,
    scrapeCount,
    targetAmount,
    scraperState,
    sendControl,
    sendPurchase,
  };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: No errors in `useSocket.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/useSocket.ts
git commit -m "refactor: remove match state, add sendPurchase to useSocket hook"
```

---

### Task 8: Update CardGrid with Buy button on matched rows

**Files:**
- Modify: `frontend/components/CardGrid.tsx`

- [ ] **Step 1: Add onBuyCard prop and Buy button column**

Replace `frontend/components/CardGrid.tsx`:

```typescript
import React, { useState } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { CardInfo } from "../hooks/useSocket";

interface CardGridProps {
  cards: CardInfo[];
  onBuyCard: (rowIndex: number) => void;
}

export default function CardGrid({ cards, onBuyCard }: CardGridProps) {
  const [buyingRow, setBuyingRow] = useState<number | null>(null);

  if (cards.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No cards yet — waiting for first refresh...</Text>
      </View>
    );
  }

  const handleBuy = (item: CardInfo) => {
    setBuyingRow(item.button_row);
    onBuyCard(item.button_row);
  };

  const renderItem = ({ item }: { item: CardInfo }) => (
    <View style={[styles.row, item.is_match && styles.matchRow]}>
      <Text style={styles.cellNumber}>#{item.card_number}</Text>
      <Text style={styles.cellBin}>{item.bin}</Text>
      <Text style={styles.cellAmount}>
        {item.currency} ${item.amount.toFixed(2)}
      </Text>
      <Text style={styles.cellDiscount}>
        {item.discount ? `${item.discount}%` : "—"}
      </Text>
      <View style={styles.cellBuy}>
        {item.is_match ? (
          <TouchableOpacity
            style={[
              styles.buyButton,
              buyingRow === item.button_row && styles.buyButtonDisabled,
            ]}
            onPress={() => handleBuy(item)}
            disabled={buyingRow === item.button_row}
          >
            <Text style={styles.buyButtonText}>
              {buyingRow === item.button_row ? "…" : "💰"}
            </Text>
          </TouchableOpacity>
        ) : (
          <Text style={styles.cellBuyPlaceholder}>—</Text>
        )}
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Live Card Grid ({cards.length} cards)</Text>
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>#</Text>
        <Text style={[styles.headerCell, { flex: 1.5 }]}>BIN</Text>
        <Text style={[styles.headerCell, { flex: 1.8 }]}>Amount</Text>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>Disc</Text>
        <Text style={[styles.headerCell, { flex: 0.7 }]}>Buy</Text>
      </View>
      <FlatList
        data={cards}
        keyExtractor={(item) => item.card_number.toString()}
        renderItem={renderItem}
        style={styles.list}
        contentContainerStyle={styles.listContent}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    maxHeight: 300,
  },
  header: {
    color: "#64748b",
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 8,
  },
  headerRow: {
    flexDirection: "row",
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  headerCell: {
    color: "#94a3b8",
    fontSize: 11,
    fontWeight: "600",
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 8,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  matchRow: {
    backgroundColor: "rgba(34, 197, 94, 0.1)",
    borderLeftWidth: 3,
    borderLeftColor: "#22c55e",
  },
  cellNumber: {
    flex: 0.8,
    color: "#94a3b8",
    fontSize: 12,
  },
  cellBin: {
    flex: 1.5,
    color: "#f1f5f9",
    fontSize: 12,
    fontWeight: "500",
  },
  cellAmount: {
    flex: 1.8,
    color: "#f1f5f9",
    fontSize: 12,
  },
  cellDiscount: {
    flex: 0.8,
    color: "#eab308",
    fontSize: 12,
  },
  cellBuy: {
    flex: 0.7,
    alignItems: "center",
  },
  buyButton: {
    backgroundColor: "#22c55e",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  buyButtonDisabled: {
    backgroundColor: "#4b5563",
  },
  buyButtonText: {
    color: "#fff",
    fontSize: 14,
  },
  cellBuyPlaceholder: {
    color: "#4b5563",
    fontSize: 12,
  },
  empty: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 24,
    alignItems: "center",
    marginBottom: 12,
  },
  emptyText: {
    color: "#64748b",
    fontSize: 14,
  },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: No errors in `CardGrid.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/CardGrid.tsx
git commit -m "feat: add Buy button on matched card rows in CardGrid"
```

---

### Task 9: Update App.tsx — remove MatchAlert, wire onBuyCard

**Files:**
- Modify: `frontend/App.tsx`

- [ ] **Step 1: Remove MatchAlert references and add handleBuyCard**

Replace `frontend/App.tsx`:

```typescript
import React, { useCallback, useState } from "react";
import { View, Text, StyleSheet, SafeAreaView, ScrollView } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSocket } from "./hooks/useSocket";
import StatusPanel from "./components/StatusPanel";
import LogStream from "./components/LogStream";
import CardGrid from "./components/CardGrid";
import SettingsPanel from "./components/SettingsPanel";

export default function App() {
  const { status, logs, lastRefresh, cards, scrapeCount, targetAmount, scraperState, sendControl, sendPurchase } = useSocket();
  const [showSettings, setShowSettings] = useState(false);

  const handleBuyCard = useCallback((rowIndex: number) => {
    sendPurchase(rowIndex);
  }, [sendPurchase]);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.title}>Gift Card Monitor</Text>
            <Text style={styles.subtitle}>
              Watching for ${targetAmount} GiftCardMall
            </Text>
          </View>
          <Text
            style={styles.settingsToggle}
            onPress={() => setShowSettings((s) => !s)}
          >
            ⚙️
          </Text>
        </View>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {/* Settings Panel */}
        {showSettings && (
          <SettingsPanel
            currentAmount={targetAmount}
            onAmountChanged={() => {}}
          />
        )}

        {/* Status */}
        <StatusPanel
          connectionStatus={status}
          lastRefresh={lastRefresh}
          scrapeCount={scrapeCount}
          cardCount={cards.length}
          targetAmount={targetAmount}
          scraperState={scraperState}
          onPause={() => sendControl("pause")}
          onResume={() => sendControl("resume")}
          onRestart={() => sendControl("restart")}
        />

        {/* Card Grid */}
        <CardGrid cards={cards} onBuyCard={handleBuyCard} />

        {/* Log Stream */}
        <LogStream logs={logs} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
    paddingHorizontal: 16,
    paddingTop: 50,
  },
  header: {
    marginBottom: 12,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    color: "#f1f5f9",
    fontSize: 24,
    fontWeight: "700",
  },
  subtitle: {
    color: "#64748b",
    fontSize: 14,
    marginTop: 2,
  },
  settingsToggle: {
    color: "#64748b",
    fontSize: 22,
    padding: 4,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 40,
  },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: No errors in `App.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/App.tsx
git commit -m "refactor: remove MatchAlert, wire onBuyCard to CardGrid"
```

---

### Task 10: Update scraper WS client — remove approval, add purchase handler

**Files:**
- Modify: `scraper/ws_client.py`

- [ ] **Step 1: Rewrite ws_client.py**

Replace `scraper/ws_client.py`:

```python
import asyncio
import logging
import time
from typing import Optional, Callable

import socketio

from .config import ScraperConfig

logger = logging.getLogger(__name__)


class ScraperWSClient:
    """
    Socket.IO client connecting the scraper to the Flask backend.

    Listens for: purchase_card, scraper_control, target_amount_changed
    Emits: status_update, cards_update, scrape_count, scraper_state
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._sio = socketio.AsyncClient()
        self._connected = False
        self._reconnect_handler: Optional[Callable] = None
        self._has_connected_before = False

        self._register_handlers()

    def set_reconnect_handler(self, handler: Callable):
        """Set a callback invoked when the client reconnects to the backend.

        The handler receives no arguments. Use it to re-sync state
        (scrape count, latest cards, scraper status) after a reconnect.
        """
        self._reconnect_handler = handler

    def _register_handlers(self):
        @self._sio.on("connect")
        def on_connect():
            self._connected = True
            logger.info("Connected to backend at %s", self.config.backend_url)
            if self._has_connected_before and self._reconnect_handler:
                try:
                    self._reconnect_handler()
                except Exception as e:
                    logger.error("Reconnect handler failed: %s", e)
            self._has_connected_before = True

        @self._sio.on("disconnect")
        def on_disconnect():
            self._connected = False
            logger.warning("Disconnected from backend")

    async def connect(self):
        """Connect to the Flask backend."""
        headers = {"X-API-Key": self.config.api_key} if self.config.api_key else {}
        await self._sio.connect(
            self.config.backend_url,
            headers=headers,
            transports=["websocket", "polling"],
        )

    async def disconnect(self):
        """Disconnect from the backend."""
        if self._connected:
            await self._sio.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_purchase_handler(self, handler: Callable[[int], None]):
        """Set a callback for purchase_card events from the backend.

        handler(row_index: int) — called when the user clicks Buy on a card.
        """

        @self._sio.on("purchase_card")
        def on_purchase_card(data: dict):
            row_index = data.get("row_index")
            if row_index is None:
                logger.warning("purchase_card received without row_index")
                return
            logger.info("Received purchase_card for row %d", row_index)
            handler(row_index)

    def set_control_handler(self, handler: Callable[[str], None]):
        """Set a callback for scraper_control events from the backend.

        handler(action: str) where action is "pause", "resume", or "restart".
        """

        @self._sio.on("scraper_control")
        def on_scraper_control(data: dict):
            action = data.get("action", "")
            logger.info("Received scraper_control: %s", action)
            handler(action)

    async def emit_scraper_state(self, state: dict):
        """Emit the current scraper state to the backend."""
        await self._sio.emit("scraper_state", state)
        logger.info("Emitted scraper_state: %s", state)

    async def emit_status(self, status: dict):
        """Emit a status update to the backend."""
        await self._sio.emit("status_update", status)

    async def emit_cards_update(self, cards: list[dict]):
        """Emit the full card list from the latest refresh."""
        await self._sio.emit("cards_update", {"cards": cards, "timestamp": time.time()})

    async def emit_scrape_count(self, count: int):
        """Emit the total scrape count."""
        await self._sio.emit("scrape_count", {"count": count})

    def set_target_amount_handler(self, handler: Callable[[float], None]):
        """Set a callback for when the target amount changes."""

        @self._sio.on("target_amount_changed")
        def on_target_amount_changed(data: dict):
            amount = data.get("amount", 50.0)
            logger.info("Received target amount change: %.2f", amount)
            handler(amount)
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from scraper.ws_client import ScraperWSClient; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add scraper/ws_client.py
git commit -m "refactor: remove approval events, add purchase_card handler to scraper WS client"
```

---

### Task 11: Update scraper main.py — remove approval loop, register purchase handler

**Files:**
- Modify: `scraper/main.py`

- [ ] **Step 1: Rewrite main.py — remove the match approval loop, add purchase_card handler**

Replace `scraper/main.py`:

```python
"""Telegram Gift Card Scraper — Entry point.

Orchestrates: connect Telethon → poll bot → parse cards → emit metrics.
Purchase commands arrive via WebSocket and execute immediately.
"""

import asyncio
import logging
import signal
import sys

from .bot_client import BotClient
from .config import ScraperConfig
from .filter_verifier import FilterVerifier
from .matcher import Matcher, GiftCardMatch
from .purchaser import Purchaser
from .refresher import Refresher
from .ws_client import ScraperWSClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scraper.main")

# Global references for signal handler
_shutdown = False
_refresher: Refresher = None


def _signal_handler(sig, frame):
    global _shutdown
    logger.info("Received signal %s, shutting down...", sig)
    _shutdown = True
    if _refresher:
        _refresher.stop()


async def main():
    global _refresher

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("Starting Telegram Gift Card Scraper")

    config = ScraperConfig()
    matcher = Matcher(target_amount=50.0)
    bot_client = BotClient(config)
    refresher = Refresher(bot_client, config)
    purchaser = Purchaser(bot_client)
    ws_client = ScraperWSClient(config)

    _refresher = refresher

    # Connect to Telegram
    try:
        await bot_client.start()
    except Exception as e:
        logger.error("Failed to start Telegram client: %s", e)
        sys.exit(1)

    bot_entity = await bot_client.get_bot_entity()

    # Navigate to Listings with GiftCardMall filter
    nav_success = await bot_client.navigate_to_listings(bot_entity)
    if not nav_success:
        logger.warning("Navigation to listings failed — will try to refresh current view")

    # Verify the filter is actually active (content-based check)
    if config.filter_verification_enabled:
        verified = False
        for attempt in range(1, config.filter_verification_retries + 1):
            verified = await bot_client.verify_filter(bot_entity)
            if verified:
                break
            logger.warning(
                "Filter verification failed (attempt %d/%d) — retrying navigation...",
                attempt,
                config.filter_verification_retries,
            )
            nav_success = await bot_client.navigate_to_listings(bot_entity)
            if not nav_success:
                logger.error("Navigation retry failed on attempt %d", attempt)

        if not verified:
            logger.error(
                "Filter verification failed after %d attempts — stopping scraper",
                config.filter_verification_retries,
            )
            try:
                await ws_client.emit_scraper_state({
                    "state": "error",
                    "reason": "filter_verification_failed",
                })
            except Exception:
                pass
            await bot_client.stop()
            sys.exit(1)
    else:
        logger.info("Filter verification disabled — skipping")

    # Connect to Flask backend
    try:
        await ws_client.connect()
        logger.info("Connected to backend")
    except Exception as e:
        logger.warning(
            "Could not connect to backend at %s: %s",
            config.backend_url,
            e,
        )
        logger.warning("Running without backend — matches will be logged only")

    # Set up target amount change handler
    ws_client.set_target_amount_handler(matcher.set_target_amount)

    # Set up refresher callbacks for metrics
    # Note: ws_client._connected is now a public property `is_connected`
    refresher.set_callbacks(
        on_cards_update=ws_client.emit_cards_update if ws_client.is_connected else None,
        on_scrape_count=ws_client.emit_scrape_count if ws_client.is_connected else None,
    )

    # When the scraper reconnects to the backend, re-sync state
    async def on_reconnect():
        if refresher.is_user_paused():
            state = "paused"
        elif refresher.last_refresh is not None:
            state = "running"
        else:
            state = "unknown"
        await ws_client.emit_scraper_state({"state": state})
        if refresher.total_refreshes > 0:
            await ws_client.emit_scrape_count({"count": refresher.total_refreshes})
    ws_client.set_reconnect_handler(lambda: asyncio.create_task(on_reconnect()))

    # --- Purchase handler (new) ---

    async def handle_purchase(row_index: int):
        """Execute a purchase immediately when the user clicks Buy."""
        logger.info("Executing purchase for row %d", row_index)

        # Reconstruct a minimal GiftCardMatch for the purchaser
        match = GiftCardMatch(
            row_index=row_index,
            card_number=None,
            card_text=f"row {row_index}",
            price=None,
            raw_message="",
        )

        try:
            success = await purchaser.purchase(match)
            if success:
                logger.info("Purchase at row %d completed successfully", row_index)
            else:
                logger.error("Purchase at row %d failed", row_index)
        except Exception as e:
            logger.error("Purchase at row %d failed with exception: %s", row_index, e)
        finally:
            # Always try to go back to listings
            try:
                await bot_client.go_back_to_listings(bot_entity)
            except Exception as e:
                logger.error("Failed to return to listings after purchase: %s", e)

    ws_client.set_purchase_handler(lambda row_index: asyncio.create_task(handle_purchase(row_index)))

    # --- Scraper control handler ---

    def on_control(action: str):
        """Handle pause/resume/restart commands from the frontend."""
        if action == "pause":
            refresher.pause_user()
            if ws_client.is_connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "paused"}))
        elif action == "resume":
            refresher.resume_user()
            if ws_client.is_connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "running"}))
        elif action == "restart":
            if ws_client.is_connected:
                asyncio.create_task(ws_client.emit_scraper_state({"state": "restarting"}))

            async def do_restart():
                ok = await bot_client.restart()
                if ws_client.is_connected:
                    if ok:
                        await ws_client.emit_scraper_state({"state": "running"})
                    else:
                        await ws_client.emit_scraper_state({"state": "error", "reason": "restart failed"})
                else:
                    logger.warning("Backend not connected after restart — state not emitted")

            asyncio.create_task(do_restart())
        else:
            logger.warning("Unknown scraper control action: %s", action)

    ws_client.set_control_handler(on_control)

    async def on_refresh_text(text: str):
        """Called on each successful refresh. Parse and emit card metrics."""
        all_cards = matcher.parse_all_cards(text)
        await refresher.emit_scrape_metrics(all_cards)

        matches = matcher.find_matches(text)
        if matches:
            for match in matches:
                logger.info(
                    "🎯 $%.2f CARD DETECTED: %s (row %d)",
                    matcher.target_amount,
                    match.card_text,
                    match.row_index,
                )

    # Start the polling loop
    logger.info("Starting poll loop for bot: %s", config.target_bot)
    await refresher.poll_loop(on_refresh_text)

    # Cleanup
    await ws_client.disconnect()
    await bot_client.stop()
    logger.info("Scraper shut down")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting")
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "import scraper.main; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add scraper/main.py
git commit -m "refactor: remove match approval loop, add direct purchase_card handler"
```

---

### Task 12: Verify the full stack starts without errors

- [ ] **Step 1: Verify all Python imports work together**

Run: `cd /home/vscode/projects/telegram-buyer && python -c "
from backend.store import MatchStore
from backend.routes import register_routes
from backend.websocket import register_socketio_events, _check_api_key
from backend.app import create_app
from backend.run import main
from scraper.ws_client import ScraperWSClient
print('All imports OK')
"`
Expected: `All imports OK`

- [ ] **Step 2: Verify frontend TypeScript compiles cleanly**

Run: `cd /home/vscode/projects/telegram-buyer/frontend && npx tsc --noEmit 2>&1`
Expected: No errors (or only pre-existing errors unrelated to our changes).

- [ ] **Step 3: Commit any remaining changes**

```bash
git status
git add -A
git commit -m "chore: final verification — all imports and types pass"
```
