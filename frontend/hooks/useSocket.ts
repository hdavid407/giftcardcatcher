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
