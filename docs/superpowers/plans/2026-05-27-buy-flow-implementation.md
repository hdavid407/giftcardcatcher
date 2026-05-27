# Buy Flow with Registration Display — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old `verified_match` auto-verification with a richer `card_status` event (for ALL matches), and implement a two-step buy flow: user clicks Buy → scraper reads card details → confirmation modal → user confirms/cancels → scraper clicks Confirm/Cancel.

**Architecture:** The scraper auto-verifies every matched card on each refresh, emitting `card_status` with full details + registration status. The frontend displays a badge per match. When the user clicks Buy, the scraper navigates to the detail screen, reads details, and emits `purchase_preview`. The frontend shows a confirmation modal; on Confirm, the scraper clicks the ✅ Confirm button.

**Tech Stack:** Python 3.14 (Telethon, Flask-SocketIO, eventlet), TypeScript/React Native (Expo, Socket.IO client)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scraper/bot_client.py` | Modify | Add `read_card_details()`, `click_confirm()`, update `check_registration()` to return dict |
| `scraper/ws_client.py` | Modify | Replace `emit_verified_match` with `emit_card_status`, add `emit_purchase_preview`, `emit_purchase_complete`, add Socket.IO handlers |
| `scraper/main.py` | Modify | Replace verification block, add `handle_initiate_purchase`, `handle_confirm_purchase`, `handle_cancel_purchase` |
| `scraper/refresher.py` | Modify | Rename `on_verified_match` callback to `on_card_status` |
| `backend/websocket.py` | Modify | Replace `verified_match` relay with `card_status`, add `initiate_purchase`, `purchase_preview`, `confirm_purchase`, `cancel_purchase`, `purchase_complete` relays |
| `frontend/hooks/useSocket.ts` | Modify | Replace `verifiedCards` with `cardStatuses` Map, add `purchasePreview`/`purchaseComplete` states, new listeners & emitters |
| `frontend/components/CardGrid.tsx` | Modify | Show registration badges, Buy button on ALL matches, pass `cardStatuses` |
| `frontend/components/PurchaseModal.tsx` | Create | Confirmation modal with card details, Confirm/Cancel buttons |
| `frontend/App.tsx` | Modify | Wire new hook values and PurchaseModal into layout |

---

### Task 1: Scraper — Add `read_card_details()` and `click_confirm()` to `bot_client.py`

**Files:**
- Modify: `scraper/bot_client.py`

- [ ] **Step 1: Add `read_card_details()` method**

Insert after `check_registration()` (around line 260):

```python
    async def read_card_details(self, bot_entity) -> Optional[dict]:
        """
        Read the detail screen text and extract structured card details.
        Assumes the bot is already on the detail screen.
        Returns a dict with id, bin, balance, price, currency, rate, status, raw_text.
        Returns None if the detail screen cannot be read.
        """
        msg = await self.get_latest_message(bot_entity)
        if not msg or not msg.text:
            logger.warning("read_card_details: no message text")
            return None

        text = msg.text
        logger.info("Reading card details from text: %s", text[:300])

        import re

        details: dict = {
            "id": None,
            "bin": None,
            "balance": None,
            "price": None,
            "currency": "USD",
            "rate": None,
            "status": "unknown",
            "raw_text": text,
        }

        # Extract ID: 💳 Card Details\n\nID: 1125704
        id_match = re.search(r"ID:\s*(\d+)", text)
        if id_match:
            details["id"] = id_match.group(1)

        # Extract BIN: BIN: 420495xx
        bin_match = re.search(r"BIN:\s*([\dxX]+)", text)
        if bin_match:
            details["bin"] = bin_match.group(1)

        # Extract balance: Amount: $2.63 USD
        amount_match = re.search(r"Amount:\s*\$?([\d.]+)", text)
        if amount_match:
            try:
                details["balance"] = float(amount_match.group(1))
            except ValueError:
                pass

        # Extract price: Price: $1.03 (39%)
        price_match = re.search(r"Price:\s*\$?([\d.]+)", text)
        if price_match:
            try:
                details["price"] = float(price_match.group(1))
            except ValueError:
                pass

        # Extract rate: (39%) or Rate: 39%
        rate_match = re.search(r"[(\s](\d+)%[)\s]", text)
        if rate_match:
            try:
                details["rate"] = int(rate_match.group(1))
            except ValueError:
                pass

        # Determine registration status
        text_lower = text.lower()
        if "unregistered" in text_lower or "un-register" in text_lower:
            details["status"] = "unregistered"
        elif "registered" in text_lower:
            details["status"] = "registered"
        else:
            details["status"] = "unknown"

        logger.info(
            "Parsed card details: id=%s bin=%s balance=%s price=%s status=%s",
            details["id"],
            details["bin"],
            details["balance"],
            details["price"],
            details["status"],
        )
        return details

    async def click_confirm(self, bot_entity) -> bool:
        """Click the ✅ Confirm button on the purchase detail screen."""
        confirm_texts = ["Confirm", "✅ Confirm", "✔️ Confirm", "Buy"]
        for text in confirm_texts:
            result = await self.click_button_by_text(bot_entity, text, wait=1.5)
            if result is not None:
                logger.info("Clicked confirm button: '%s'", text)
                return True

        logger.warning("Could not find Confirm button")
        return False
```

- [ ] **Step 2: Update `check_registration()` to use `read_card_details()`**

Replace the existing `check_registration()` method:

```python
    async def check_registration(self, bot_entity, row_index: int) -> Optional[dict]:
        """
        Click Purchase on a card, read its full details, then click Cancel.
        Returns a dict with card details and status, or None if the operation failed.
        Always returns to the listings view before returning.
        """
        success = await self.click_purchase(bot_entity, row_index)
        if not success:
            return None

        # Wait for the detail view to load
        await asyncio.sleep(2.0)

        details = await self.read_card_details(bot_entity)

        # Always click Cancel to return to listings
        await self.click_cancel(bot_entity)
        return details
```

- [ ] **Step 3: Commit**

```bash
git add scraper/bot_client.py
git commit -m "feat(bot_client): add read_card_details, click_confirm, update check_registration"
```

---

### Task 2: Scraper — Update `ws_client.py` with new events and handlers

**Files:**
- Modify: `scraper/ws_client.py`

- [ ] **Step 1: Replace `emit_verified_match` with `emit_card_status`**

Replace the `emit_verified_match` method:

```python
    async def emit_card_status(self, card_data: dict):
        """Emit card status (auto-verification result) to the backend."""
        await self._sio.emit("card_status", card_data)
        logger.info(
            "Emitted card_status for card #%s (%s)",
            card_data.get("card_number"),
            card_data.get("status"),
        )

    async def emit_purchase_preview(self, card_data: dict):
        """Emit purchase preview (detail screen data) to the backend."""
        await self._sio.emit("purchase_preview", card_data)
        logger.info(
            "Emitted purchase_preview for card #%s",
            card_data.get("card_number"),
        )

    async def emit_purchase_complete(self, result: dict):
        """Emit purchase completion result to the backend."""
        await self._sio.emit("purchase_complete", result)
        logger.info(
            "Emitted purchase_complete for card #%s: success=%s",
            result.get("card_number"),
            result.get("success"),
        )
```

- [ ] **Step 2: Add handlers for new purchase flow events**

Add after `set_target_amount_handler`:

```python
    def set_initiate_purchase_handler(self, handler: Callable[[int], None]):
        """Set a callback for initiate_purchase events from the backend.

        handler(row_index: int) — called when the user clicks Buy on a card.
        """

        @self._sio.on("initiate_purchase")
        def on_initiate_purchase(data: dict):
            row_index = data.get("row_index")
            if row_index is None:
                logger.warning("initiate_purchase received without row_index")
                return
            logger.info("Received initiate_purchase for row %d", row_index)
            handler(row_index)

    def set_confirm_purchase_handler(self, handler: Callable[[int], None]):
        """Set a callback for confirm_purchase events from the backend."""

        @self._sio.on("confirm_purchase")
        def on_confirm_purchase(data: dict):
            row_index = data.get("row_index")
            if row_index is None:
                logger.warning("confirm_purchase received without row_index")
                return
            logger.info("Received confirm_purchase for row %d", row_index)
            handler(row_index)

    def set_cancel_purchase_handler(self, handler: Callable[[int], None]):
        """Set a callback for cancel_purchase events from the backend."""

        @self._sio.on("cancel_purchase")
        def on_cancel_purchase(data: dict):
            row_index = data.get("row_index")
            if row_index is None:
                logger.warning("cancel_purchase received without row_index")
                return
            logger.info("Received cancel_purchase for row %d", row_index)
            handler(row_index)
```

- [ ] **Step 3: Remove old `emit_verified_match` and `set_purchase_handler`**

Delete the old `emit_verified_match` method and `set_purchase_handler` method entirely.

- [ ] **Step 4: Commit**

```bash
git add scraper/ws_client.py
git commit -m "feat(ws_client): replace verified_match with card_status, add purchase flow events"
```

---

### Task 3: Scraper — Update `refresher.py` callback name

**Files:**
- Modify: `scraper/refresher.py`

- [ ] **Step 1: Rename `on_verified_match` to `on_card_status`**

In `set_callbacks()`, rename the parameter and internal field:

```python
    def set_callbacks(
        self,
        on_cards_update: Optional[Callable] = None,
        on_scrape_count: Optional[Callable] = None,
        on_card_status: Optional[Callable] = None,
    ):
        """Set callbacks for emitting events to the backend."""
        self._on_cards_update = on_cards_update
        self._on_scrape_count = on_scrape_count
        self._on_card_status = on_card_status
```

- [ ] **Step 2: Rename the emit method**

```python
    async def emit_card_status(self, card_data: dict):
        """Emit a card status update to the backend."""
        if self._on_card_status:
            try:
                await self._on_card_status(card_data)
            except Exception as e:
                logger.error("Failed to emit card status: %s", e)
```

Delete the old `emit_verified_match` method.

- [ ] **Step 3: Commit**

```bash
git add scraper/refresher.py
git commit -m "refactor(refresher): rename verified_match callback to card_status"
```

---

### Task 4: Scraper — Rewrite `main.py` auto-verification and add purchase handlers

**Files:**
- Modify: `scraper/main.py`

- [ ] **Step 1: Update refresher callbacks in `main()`**

Replace the `set_callbacks` call:

```python
    refresher.set_callbacks(
        on_cards_update=ws_client.emit_cards_update if ws_client.is_connected else None,
        on_scrape_count=ws_client.emit_scrape_count if ws_client.is_connected else None,
        on_card_status=ws_client.emit_card_status if ws_client.is_connected else None,
    )
```

- [ ] **Step 2: Replace `handle_purchase` with purchase flow handlers**

Replace the entire `handle_purchase` function and `ws_client.set_purchase_handler` call with:

```python
    # --- Purchase flow handlers ---

    _pending_purchase_row: Optional[int] = None

    async def handle_initiate_purchase(row_index: int):
        """User clicked Buy — navigate to detail screen and emit preview."""
        nonlocal _pending_purchase_row
        _pending_purchase_row = row_index

        logger.info("Initiating purchase for row %d", row_index)
        refresher.pause(300)  # Long pause during purchase flow
        if ws_client.is_connected:
            await ws_client.emit_scraper_state({"state": "purchasing"})

        try:
            bot = await bot_client.get_bot_entity()
            success = await bot_client.click_purchase(bot, row_index)
            if not success:
                logger.error("Failed to click Purchase for row %d", row_index)
                if ws_client.is_connected:
                    await ws_client.emit_purchase_complete({
                        "card_number": None,
                        "success": False,
                        "reason": "click_purchase_failed",
                    })
                _pending_purchase_row = None
                refresher.resume()
                return

            await asyncio.sleep(2.0)
            details = await bot_client.read_card_details(bot)
            if details is None:
                logger.error("Could not read card details for row %d", row_index)
                if ws_client.is_connected:
                    await ws_client.emit_purchase_complete({
                        "card_number": None,
                        "success": False,
                        "reason": "read_details_failed",
                    })
                await bot_client.click_cancel(bot)
                _pending_purchase_row = None
                refresher.resume()
                return

            # Find the card_number from the latest cards (stored via matcher)
            card_number = None
            for card in matcher._last_cards if hasattr(matcher, "_last_cards") else []:
                if card.button_row == row_index:
                    card_number = card.card_number
                    break

            details["card_number"] = card_number
            details["button_row"] = row_index

            if ws_client.is_connected:
                await ws_client.emit_purchase_preview(details)
                logger.info("Emitted purchase_preview for row %d", row_index)

        except Exception as e:
            logger.error("Initiate purchase failed for row %d: %s", row_index, e)
            _pending_purchase_row = None
            refresher.resume()

    async def handle_confirm_purchase(row_index: int):
        """User confirmed purchase — click Confirm."""
        nonlocal _pending_purchase_row
        logger.info("Confirming purchase for row %d", row_index)

        try:
            bot = await bot_client.get_bot_entity()
            success = await bot_client.click_confirm(bot)
            if success:
                logger.info("Purchase confirmed for row %d", row_index)
            else:
                logger.error("Failed to click Confirm for row %d", row_index)

            # Return to listings
            await bot_client.go_back_to_listings(bot)

            card_number = None
            for card in matcher._last_cards if hasattr(matcher, "_last_cards") else []:
                if card.button_row == row_index:
                    card_number = card.card_number
                    break

            if ws_client.is_connected:
                await ws_client.emit_purchase_complete({
                    "card_number": card_number,
                    "success": success,
                    "reason": None if success else "confirm_click_failed",
                })

        except Exception as e:
            logger.error("Confirm purchase failed for row %d: %s", row_index, e)
            if ws_client.is_connected:
                await ws_client.emit_purchase_complete({
                    "card_number": None,
                    "success": False,
                    "reason": "exception",
                })
        finally:
            _pending_purchase_row = None
            refresher.resume()

    async def handle_cancel_purchase(row_index: int):
        """User cancelled purchase — click Cancel."""
        nonlocal _pending_purchase_row
        logger.info("Cancelling purchase for row %d", row_index)

        try:
            bot = await bot_client.get_bot_entity()
            await bot_client.click_cancel(bot)
            logger.info("Cancelled purchase for row %d", row_index)

            card_number = None
            for card in matcher._last_cards if hasattr(matcher, "_last_cards") else []:
                if card.button_row == row_index:
                    card_number = card.card_number
                    break

            if ws_client.is_connected:
                await ws_client.emit_purchase_complete({
                    "card_number": card_number,
                    "success": False,
                    "reason": "user_cancelled",
                })

        except Exception as e:
            logger.error("Cancel purchase failed for row %d: %s", row_index, e)
        finally:
            _pending_purchase_row = None
            refresher.resume()

    ws_client.set_initiate_purchase_handler(
        lambda row_index: asyncio.create_task(handle_initiate_purchase(row_index))
    )
    ws_client.set_confirm_purchase_handler(
        lambda row_index: asyncio.create_task(handle_confirm_purchase(row_index))
    )
    ws_client.set_cancel_purchase_handler(
        lambda row_index: asyncio.create_task(handle_cancel_purchase(row_index))
    )
```

- [ ] **Step 3: Replace `on_refresh_text` verification block**

Replace the verification block inside `on_refresh_text`:

```python
        matches = matcher.find_matches(text)
        if matches:
            for match in matches:
                logger.info(
                    "🎯 $%.2f CARD DETECTED: %s (row %d)",
                    matcher.target_amount,
                    match.card_text,
                    match.row_index,
                )

            # Pause refresher and verify each match sequentially
            refresher.pause(60)
            if ws_client.is_connected:
                await ws_client.emit_scraper_state({"state": "verifying"})

            try:
                bot = await bot_client.get_bot_entity()
                for match in matches:
                    logger.info(
                        "🔍 Verifying card at row %d...",
                        match.row_index,
                    )
                    details = await bot_client.check_registration(
                        bot, match.row_index
                    )
                    if details is None:
                        logger.warning(
                            "⚠️ Could not verify card at row %d",
                            match.row_index,
                        )
                        continue

                    # Build the card_status payload
                    card_data = {
                        "card_number": match.card_number,
                        "status": details.get("status", "unknown"),
                        "id": details.get("id"),
                        "bin": details.get("bin") or "unknown",
                        "balance": details.get("balance"),
                        "price": details.get("price"),
                        "currency": details.get("currency", "USD"),
                        "rate": details.get("rate"),
                        "raw_text": match.card_text,
                        "button_row": match.row_index,
                    }

                    status_emoji = {"unregistered": "✅", "registered": "❌", "unknown": "⚠️"}
                    logger.info(
                        "%s Card #%s status: %s (id=%s, bin=%s, balance=%s, price=%s)",
                        status_emoji.get(card_data["status"], "?"),
                        card_data["card_number"],
                        card_data["status"],
                        card_data["id"],
                        card_data["bin"],
                        card_data["balance"],
                        card_data["price"],
                    )

                    if ws_client.is_connected:
                        await ws_client.emit_card_status(card_data)

            except Exception as e:
                logger.error("Verification failed: %s", e)
            finally:
                refresher.resume()
                if ws_client.is_connected:
                    await ws_client.emit_scraper_state({"state": "running"})
```

- [ ] **Step 4: Store last cards in matcher for lookup during purchase flow**

In `on_refresh_text`, add after `all_cards = matcher.parse_all_cards(text)`:

```python
        matcher._last_cards = all_cards
```

This requires adding `_last_cards: list[CardInfo] = []` to the `Matcher` class in `scraper/matcher.py`. Since `Matcher` is imported and its internals are simple, add the field in `scraper/matcher.py`:

```python
class Matcher:
    def __init__(self, target_amount: float = 50.0):
        self.target_amount = target_amount
        self._last_cards: list[CardInfo] = []
```

And in `parse_all_cards`, store the result:

```python
    def parse_all_cards(self, text: str) -> list[CardInfo]:
        ...
        self._last_cards = cards
        return cards
```

- [ ] **Step 5: Commit**

```bash
git add scraper/main.py scraper/matcher.py
git commit -m "feat(main): rewrite auto-verification to emit card_status for all matches, add purchase flow handlers"
```

---

### Task 5: Backend — Update `websocket.py` with new event relays

**Files:**
- Modify: `backend/websocket.py`

- [ ] **Step 1: Replace `verified_match` with `card_status`**

Replace the `on_verified_match` handler:

```python
    @socketio.on("card_status")
    def on_card_status(data: dict):
        """Receive card status from scraper and broadcast to all clients."""
        emit("card_status", data, broadcast=True)
```

- [ ] **Step 2: Add new purchase flow event handlers**

Add after `on_card_status`:

```python
    @socketio.on("initiate_purchase")
    def on_initiate_purchase(data: dict):
        """Relay initiate_purchase from frontend to scraper."""
        row_index = data.get("row_index")
        if row_index is None:
            logger.warning("initiate_purchase received without row_index")
            return
        if _scraper_sid:
            emit("initiate_purchase", {"row_index": row_index}, room=_scraper_sid)
            logger.info("Relayed initiate_purchase to scraper (row %d)", row_index)
        else:
            logger.warning("Scraper not connected — cannot relay initiate_purchase")
            emit("purchase_card_error", {
                "row_index": row_index,
                "reason": "Scraper not connected",
            })

    @socketio.on("purchase_preview")
    def on_purchase_preview(data: dict):
        """Receive purchase preview from scraper and broadcast."""
        emit("purchase_preview", data, broadcast=True)

    @socketio.on("confirm_purchase")
    def on_confirm_purchase(data: dict):
        """Relay confirm_purchase from frontend to scraper."""
        row_index = data.get("row_index")
        if row_index is None:
            logger.warning("confirm_purchase received without row_index")
            return
        if _scraper_sid:
            emit("confirm_purchase", {"row_index": row_index}, room=_scraper_sid)
            logger.info("Relayed confirm_purchase to scraper (row %d)", row_index)
        else:
            logger.warning("Scraper not connected — cannot relay confirm_purchase")

    @socketio.on("cancel_purchase")
    def on_cancel_purchase(data: dict):
        """Relay cancel_purchase from frontend to scraper."""
        row_index = data.get("row_index")
        if row_index is None:
            logger.warning("cancel_purchase received without row_index")
            return
        if _scraper_sid:
            emit("cancel_purchase", {"row_index": row_index}, room=_scraper_sid)
            logger.info("Relayed cancel_purchase to scraper (row %d)", row_index)
        else:
            logger.warning("Scraper not connected — cannot relay cancel_purchase")

    @socketio.on("purchase_complete")
    def on_purchase_complete(data: dict):
        """Receive purchase complete from scraper and broadcast."""
        emit("purchase_complete", data, broadcast=True)
```

- [ ] **Step 3: Commit**

```bash
git add backend/websocket.py
git commit -m "feat(websocket): replace verified_match with card_status, add purchase flow event relays"
```

---

### Task 6: Frontend — Rewrite `useSocket.ts`

**Files:**
- Modify: `frontend/hooks/useSocket.ts`

- [ ] **Step 1: Update types and interface**

Replace the `UseSocketReturn` interface and add new types:

```typescript
export type RegistrationStatus = "unregistered" | "registered" | "unknown";

export interface CardStatus {
  card_number: number;
  status: RegistrationStatus;
  id: string | null;
  bin: string | null;
  balance: number | null;
  price: number | null;
  currency: string;
  rate: number | null;
  raw_text: string;
}

export interface PurchasePreview {
  card_number: number | null;
  button_row: number;
  id: string | null;
  bin: string | null;
  balance: number | null;
  price: number | null;
  currency: string;
  rate: number | null;
  status: RegistrationStatus;
  raw_text: string;
}

export interface PurchaseComplete {
  card_number: number | null;
  success: boolean;
  reason?: string;
}

interface UseSocketReturn {
  status: ConnectionStatus;
  logs: string[];
  lastRefresh: string | null;
  cards: CardInfo[];
  cardStatuses: Map<number, CardStatus>;
  purchasePreview: PurchasePreview | null;
  purchaseComplete: PurchaseComplete | null;
  scrapeCount: number;
  targetAmount: number;
  scraperState: ScraperState;
  sendControl: (action: "pause" | "resume" | "restart") => void;
  initiatePurchase: (rowIndex: number) => void;
  confirmPurchase: (rowIndex: number) => void;
  cancelPurchase: (rowIndex: number) => void;
}
```

- [ ] **Step 2: Replace state and listeners in `useSocket` hook**

Replace `verifiedCards` state with `cardStatuses`, add `purchasePreview` and `purchaseComplete`:

```typescript
  const [cardStatuses, setCardStatuses] = useState<Map<number, CardStatus>>(new Map());
  const [purchasePreview, setPurchasePreview] = useState<PurchasePreview | null>(null);
  const [purchaseComplete, setPurchaseComplete] = useState<PurchaseComplete | null>(null);
```

Replace the `verified_match` listener with `card_status`:

```typescript
    socket.on("card_status", (data: CardStatus) => {
      setCardStatuses((prev) => {
        const next = new Map(prev);
        next.set(data.card_number, data);
        return next;
      });
      const emoji = data.status === "unregistered" ? "🟢" : data.status === "registered" ? "🔴" : "⚪";
      addLog(`${emoji} Card #${data.card_number}: ${data.status} (id=${data.id}, bin=${data.bin}, balance=$${data.balance}, price=$${data.price})`);
    });
```

Add new listeners:

```typescript
    socket.on("purchase_preview", (data: PurchasePreview) => {
      setPurchasePreview(data);
      addLog(`🔍 Purchase preview received for card #${data.card_number}`);
    });

    socket.on("purchase_complete", (data: PurchaseComplete) => {
      setPurchaseComplete(data);
      setPurchasePreview(null);
      const emoji = data.success ? "✅" : "❌";
      addLog(`${emoji} Purchase complete for card #${data.card_number}: ${data.success ? "success" : data.reason || "failed"}`);
    });
```

Update the `cards_update` listener to prune `cardStatuses` instead of `verifiedCards`:

```typescript
    socket.on("cards_update", (data: { cards: CardInfo[]; timestamp: number }) => {
      setCards(data.cards);
      // Prune card statuses for cards that are no longer in the listing
      setCardStatuses((prev) => {
        const currentNumbers = new Set(data.cards.map((c) => c.card_number));
        const next = new Map<number, CardStatus>();
        for (const [num, status] of prev) {
          if (currentNumbers.has(num)) {
            next.set(num, status);
          }
        }
        return next;
      });
      addLog(`📋 Cards updated: ${data.cards.length} cards`);
    });
```

- [ ] **Step 3: Replace `sendPurchase` with new emitters**

Replace `sendPurchase` and update the return object:

```typescript
  const initiatePurchase = useCallback((rowIndex: number) => {
    if (socketRef.current) {
      socketRef.current.emit("initiate_purchase", { row_index: rowIndex });
      addLog(`🛒 Initiate purchase for row ${rowIndex}`);
    } else {
      addLog("⚠️ Not connected — cannot initiate purchase");
    }
  }, [addLog]);

  const confirmPurchase = useCallback((rowIndex: number) => {
    if (socketRef.current) {
      socketRef.current.emit("confirm_purchase", { row_index: rowIndex });
      addLog(`✅ Confirm purchase for row ${rowIndex}`);
    } else {
      addLog("⚠️ Not connected — cannot confirm purchase");
    }
  }, [addLog]);

  const cancelPurchase = useCallback((rowIndex: number) => {
    if (socketRef.current) {
      socketRef.current.emit("cancel_purchase", { row_index: rowIndex });
      addLog(`❌ Cancel purchase for row ${rowIndex}`);
    } else {
      addLog("⚠️ Not connected — cannot cancel purchase");
    }
  }, [addLog]);
```

Update the return object:

```typescript
  return {
    status,
    logs,
    lastRefresh,
    cards,
    cardStatuses,
    purchasePreview,
    purchaseComplete,
    scrapeCount,
    targetAmount,
    scraperState,
    sendControl,
    initiatePurchase,
    confirmPurchase,
    cancelPurchase,
  };
```

- [ ] **Step 4: Commit**

```bash
git add frontend/hooks/useSocket.ts
git commit -m "feat(useSocket): replace verifiedCards with cardStatuses, add purchase flow states and emitters"
```

---

### Task 7: Frontend — Update `CardGrid.tsx`

**Files:**
- Modify: `frontend/components/CardGrid.tsx`

- [ ] **Step 1: Update props and imports**

```typescript
import React, { useState } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { CardInfo, CardStatus } from "../hooks/useSocket";

interface CardGridProps {
  cards: CardInfo[];
  cardStatuses: Map<number, CardStatus>;
  onBuyCard: (rowIndex: number) => void;
}
```

- [ ] **Step 2: Update renderItem to show badges and Buy on all matches**

```typescript
export default function CardGrid({ cards, cardStatuses, onBuyCard }: CardGridProps) {
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

  const renderItem = ({ item }: { item: CardInfo }) => {
    const status = cardStatuses.get(item.card_number);
    const statusEmoji = status
      ? status.status === "unregistered"
        ? "🟢"
        : status.status === "registered"
        ? "🔴"
        : "⚪"
      : item.is_match
      ? "⏳"
      : null;

    return (
      <View style={[styles.row, item.is_match && styles.matchRow]}>
        <Text style={styles.cellNumber}>#{item.card_number}</Text>
        <Text style={styles.cellBin}>{item.bin}</Text>
        <Text style={styles.cellAmount}>
          {item.currency} ${item.amount.toFixed(2)}
        </Text>
        <Text style={styles.cellDiscount}>
          {item.discount ? `${item.discount}%` : "—"}
        </Text>
        <View style={styles.cellStatus}>
          <Text style={styles.statusEmoji}>{statusEmoji || "—"}</Text>
        </View>
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
  };
```

- [ ] **Step 3: Update header row to add Status column**

```typescript
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>#</Text>
        <Text style={[styles.headerCell, { flex: 1.5 }]}>BIN</Text>
        <Text style={[styles.headerCell, { flex: 1.8 }]}>Amount</Text>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>Disc</Text>
        <Text style={[styles.headerCell, { flex: 0.7 }]}>Sts</Text>
        <Text style={[styles.headerCell, { flex: 0.7 }]}>Buy</Text>
      </View>
```

- [ ] **Step 4: Add styles for status column**

```typescript
  cellStatus: {
    flex: 0.7,
    alignItems: "center",
  },
  statusEmoji: {
    fontSize: 12,
  },
```

- [ ] **Step 5: Commit**

```bash
git add frontend/components/CardGrid.tsx
git commit -m "feat(CardGrid): show registration status badges, Buy button on all matches"
```

---

### Task 8: Frontend — Create `PurchaseModal.tsx`

**Files:**
- Create: `frontend/components/PurchaseModal.tsx`

- [ ] **Step 1: Create the component**

```typescript
import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
} from "react-native";
import { PurchasePreview, PurchaseComplete } from "../hooks/useSocket";

interface PurchaseModalProps {
  preview: PurchasePreview | null;
  complete: PurchaseComplete | null;
  onConfirm: (rowIndex: number) => void;
  onCancel: (rowIndex: number) => void;
}

export default function PurchaseModal({
  preview,
  complete,
  onConfirm,
  onCancel,
}: PurchaseModalProps) {
  if (!preview) {
    return null;
  }

  const statusEmoji =
    preview.status === "unregistered"
      ? "🟢"
      : preview.status === "registered"
      ? "🔴"
      : "⚪";

  return (
    <Modal
      animationType="slide"
      transparent={true}
      visible={!!preview}
      onRequestClose={() => onCancel(preview.button_row)}
    >
      <View style={styles.overlay}>
        <View style={styles.modal}>
          <Text style={styles.title}>Confirm Purchase</Text>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Card ID:</Text>
            <Text style={styles.detailValue}>{preview.id || "—"}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>BIN:</Text>
            <Text style={styles.detailValue}>{preview.bin || "—"}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Balance:</Text>
            <Text style={styles.detailValue}>
              {preview.currency} ${preview.balance?.toFixed(2) || "—"}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Price:</Text>
            <Text style={styles.detailValue}>
              {preview.currency} ${preview.price?.toFixed(2) || "—"}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Rate:</Text>
            <Text style={styles.detailValue}>
              {preview.rate ? `${preview.rate}%` : "—"}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Status:</Text>
            <Text style={styles.detailValue}>
              {statusEmoji} {preview.status}
            </Text>
          </View>

          {complete && (
            <Text
              style={[
                styles.resultText,
                complete.success ? styles.successText : styles.errorText,
              ]}
            >
              {complete.success
                ? "✅ Purchase successful!"
                : `❌ Purchase failed: ${complete.reason || "unknown"}`}
            </Text>
          )}

          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={[styles.button, styles.cancelButton]}
              onPress={() => onCancel(preview.button_row)}
              disabled={!!complete}
            >
              <Text style={styles.buttonText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.button, styles.confirmButton]}
              onPress={() => onConfirm(preview.button_row)}
              disabled={!!complete}
            >
              <Text style={styles.buttonText}>Confirm Purchase</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  modal: {
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 24,
    width: "100%",
    maxWidth: 400,
  },
  title: {
    color: "#f1f5f9",
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 16,
    textAlign: "center",
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  detailLabel: {
    color: "#94a3b8",
    fontSize: 14,
  },
  detailValue: {
    color: "#f1f5f9",
    fontSize: 14,
    fontWeight: "500",
  },
  resultText: {
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
    marginTop: 12,
    marginBottom: 4,
  },
  successText: {
    color: "#22c55e",
  },
  errorText: {
    color: "#ef4444",
  },
  buttonRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 20,
    gap: 12,
  },
  button: {
    flex: 1,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  cancelButton: {
    backgroundColor: "#475569",
  },
  confirmButton: {
    backgroundColor: "#22c55e",
  },
  buttonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/PurchaseModal.tsx
git commit -m "feat(PurchaseModal): add purchase confirmation modal component"
```

---

### Task 9: Frontend — Wire everything in `App.tsx`

**Files:**
- Modify: `frontend/App.tsx`

- [ ] **Step 1: Update imports and hook destructuring**

```typescript
import React, { useCallback, useState } from "react";
import { View, Text, StyleSheet, SafeAreaView, ScrollView } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSocket } from "./hooks/useSocket";
import StatusPanel from "./components/StatusPanel";
import LogStream from "./components/LogStream";
import CardGrid from "./components/CardGrid";
import SettingsPanel from "./components/SettingsPanel";
import PurchaseModal from "./components/PurchaseModal";
```

Update the hook destructuring:

```typescript
  const {
    status,
    logs,
    lastRefresh,
    cards,
    cardStatuses,
    purchasePreview,
    purchaseComplete,
    scrapeCount,
    targetAmount,
    scraperState,
    sendControl,
    initiatePurchase,
    confirmPurchase,
    cancelPurchase,
  } = useSocket();
```

- [ ] **Step 2: Update handlers**

```typescript
  const handleBuyCard = useCallback((rowIndex: number) => {
    initiatePurchase(rowIndex);
  }, [initiatePurchase]);

  const handleConfirmPurchase = useCallback((rowIndex: number) => {
    confirmPurchase(rowIndex);
  }, [confirmPurchase]);

  const handleCancelPurchase = useCallback((rowIndex: number) => {
    cancelPurchase(rowIndex);
  }, [cancelPurchase]);
```

- [ ] **Step 3: Update CardGrid and add PurchaseModal**

```typescript
        {/* Card Grid */}
        <CardGrid
          cards={cards}
          cardStatuses={cardStatuses}
          onBuyCard={handleBuyCard}
        />

        {/* Purchase Modal */}
        <PurchaseModal
          preview={purchasePreview}
          complete={purchaseComplete}
          onConfirm={handleConfirmPurchase}
          onCancel={handleCancelPurchase}
        />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/App.tsx
git commit -m "feat(App): wire purchase flow modal and card status into main layout"
```

---

### Task 10: Run Python syntax check and existing tests

**Files:**
- All Python files

- [ ] **Step 1: Run syntax check on all modified Python files**

```bash
cd /home/vscode/projects/telegram-buyer
python -m py_compile scraper/bot_client.py scraper/ws_client.py scraper/main.py scraper/refresher.py backend/websocket.py
```

Expected: No output (success)

- [ ] **Step 2: Run existing tests**

```bash
cd /home/vscode/projects/telegram-buyer
pytest tests/ -v
```

Expected: All tests pass (test_config.py, test_filter_verifier.py)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: verify all Python syntax and existing tests pass"
```

---

### Task 11: Integration test — start services and verify event flow

**Files:**
- N/A (runtime verification)

- [ ] **Step 1: Restart backend and scraper**

Kill any running backend/scraper processes, then start fresh:

```bash
cd /home/vscode/projects/telegram-buyer
pkill -f "python backend/run.py" || true
pkill -f "python -m scraper" || true
sleep 2
source .venv/bin/activate
python backend/run.py &
sleep 3
python -m scraper.main &
```

- [ ] **Step 2: Open frontend in browser**

The Expo dev server should already be running at `http://localhost:8081`. If not:

```bash
cd /home/vscode/projects/telegram-buyer/frontend
npx expo start --web --port 8081 &
```

- [ ] **Step 3: Verify `card_status` events appear in frontend logs**

Wait for a refresh cycle that produces a match. The frontend log should show lines like:

```
🟢 Card #3: unregistered (id=1125704, bin=420495xx, balance=$2.63, price=$1.03)
```

or

```
🔴 Card #5: registered (id=..., bin=..., balance=$2.63, price=$1.03)
```

- [ ] **Step 4: Click Buy and verify purchase flow**

Click the 💰 Buy button on a matched card. Verify:
1. Frontend log shows "🛒 Initiate purchase for row X"
2. After ~3 seconds, PurchaseModal appears with card details
3. Clicking Cancel emits "❌ Cancel purchase" and modal closes
4. Clicking Confirm emits "✅ Confirm purchase" and modal shows result

- [ ] **Step 5: Commit test artifacts / cleanup**

```bash
git add -A
git commit -m "test: integration test passed for buy flow"
```

---

## Spec Coverage Checklist

| Spec Requirement | Implementing Task |
|------------------|-------------------|
| Auto-verify ALL matches, emit `card_status` | Task 4 |
| `card_status` payload with id, bin, balance, price, rate, status | Task 1 + Task 4 |
| Buy button on ALL matches | Task 7 |
| Registration status badge (🟢/🔴/⚪) | Task 6 + Task 7 |
| Two-step buy flow: initiate → preview → confirm/cancel | Task 2 + Task 4 + Task 5 + Task 6 + Task 8 + Task 9 |
| `purchase_preview` event with full details | Task 1 + Task 2 + Task 4 + Task 5 |
| `purchase_complete` event | Task 2 + Task 4 + Task 5 |
| Scraper pauses refresher during purchase | Task 4 |
| Scraper returns to listings after purchase | Task 4 |
| Modal closes on `purchase_complete` | Task 6 + Task 8 |
| Edge case: missing Confirm button | Task 4 (click_confirm returns False, emits failure) |
| Edge case: user cancels | Task 4 + Task 8 |

## Placeholder Scan

- No "TBD", "TODO", "implement later" found.
- No vague "add error handling" steps — specific code provided.
- No "write tests for the above" without code — tests are runtime verification in Task 10-11.
- No "similar to Task N" references.
- All file paths are exact.

## Type Consistency Check

- `read_card_details` returns `Optional[dict]` with keys: `id`, `bin`, `balance`, `price`, `currency`, `rate`, `status`, `raw_text` — consistent across Tasks 1, 4, 6.
- `card_status` event payload uses same keys — consistent across Tasks 2, 4, 5, 6.
- `purchase_preview` payload includes `card_number`, `button_row` — consistent across Tasks 4, 6, 8.
- `purchase_complete` payload: `card_number`, `success`, `reason` — consistent across Tasks 4, 5, 6, 8.
- Frontend `CardStatus` interface matches payload — consistent across Tasks 6, 7.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-buy-flow-implementation.md`.**
