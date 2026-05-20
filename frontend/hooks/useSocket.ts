import { useEffect, useRef, useState, useCallback } from "react";
import { io, Socket } from "socket.io-client";
import { MatchData } from "../api/client";

const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:5000";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface UseSocketReturn {
  status: ConnectionStatus;
  match: MatchData | null;
  logs: string[];
  lastRefresh: string | null;
  resetMatch: () => void;
}

export function useSocket(): UseSocketReturn {
  const socketRef = useRef<Socket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [match, setMatch] = useState<MatchData | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);

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

    socket.on("match_found", (data: MatchData) => {
      setMatch(data);
      addLog(`🔔 MATCH: ${data.card_text} (${data.price || "no price"})`);
    });

    socket.on("match_rejected", (data: { reason: string }) => {
      addLog(`⚠️ Match rejected: ${data.reason}`);
    });

    socket.on("purchase_approved", (data: MatchData) => {
      addLog(`✅ Purchase APPROVED for ${data.card_text}`);
      setMatch(null);
    });

    socket.on("purchase_denied", (data: MatchData) => {
      addLog(`❌ Purchase DENIED for ${data.card_text}`);
      setMatch(null);
    });

    socket.on("match_expired", (data: MatchData) => {
      addLog(`⏰ Match EXPIRED for ${data.card_text}`);
      setMatch(null);
    });

    socket.on("status_update", (data: { last_refresh?: string }) => {
      if (data.last_refresh) {
        setLastRefresh(data.last_refresh);
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [addLog]);

  const resetMatch = useCallback(() => {
    setMatch(null);
  }, []);

  return { status, match, logs, lastRefresh, resetMatch };
}
