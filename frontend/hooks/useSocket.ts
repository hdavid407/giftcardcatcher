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
  autoBuyEnabled: boolean;
  sendControl: (action: "pause" | "resume" | "restart") => void;
  initiatePurchase: (rowIndex: number) => void;
  confirmPurchase: (rowIndex: number) => void;
  cancelPurchase: (rowIndex: number) => void;
  toggleAutoBuy: (enabled: boolean) => void;
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
  const [cardStatuses, setCardStatuses] = useState<Map<number, CardStatus>>(new Map());
  const [purchasePreview, setPurchasePreview] = useState<PurchasePreview | null>(null);
  const [purchaseComplete, setPurchaseComplete] = useState<PurchaseComplete | null>(null);
  const [autoBuyEnabled, setAutoBuyEnabled] = useState<boolean>(false);

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

    socket.on("card_status", (data: CardStatus) => {
      setCardStatuses((prev) => {
        const next = new Map(prev);
        next.set(data.card_number, data);
        return next;
      });
      const emoji = data.status === "unregistered" ? "🟢" : data.status === "registered" ? "🔴" : "⚪";
      addLog(`${emoji} Card #${data.card_number}: ${data.status} (id=${data.id}, bin=${data.bin}, balance=$${data.balance}, price=$${data.price})`);
    });

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

    socket.on("auto_buy_status", (data: { enabled: boolean; reason?: string }) => {
      setAutoBuyEnabled(data.enabled);
      const emoji = data.enabled ? "🤖" : "🚫";
      const reasonText = data.reason ? ` (${data.reason})` : "";
      addLog(`${emoji} Auto-buy ${data.enabled ? "enabled" : "disabled"}${reasonText}`);
    });

    return () => {
      socket.disconnect();
    };
  }, [addLog]);

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

  const sendControl = useCallback((action: "pause" | "resume" | "restart") => {
    if (socketRef.current) {
      socketRef.current.emit("scraper_control", { action });
    }
  }, []);

  const toggleAutoBuy = useCallback((enabled: boolean) => {
    if (socketRef.current) {
      socketRef.current.emit("toggle_auto_buy", { enabled });
      addLog(`${enabled ? "🤖" : "🚫"} Auto-buy toggle requested: ${enabled ? "ON" : "OFF"}`);
    }
  }, [addLog]);

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
    autoBuyEnabled,
    sendControl,
    initiatePurchase,
    confirmPurchase,
    cancelPurchase,
    toggleAutoBuy,
  };
}
