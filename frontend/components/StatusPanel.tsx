import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { ConnectionStatus, ScraperState } from "../hooks/useSocket";

interface StatusPanelProps {
  connectionStatus: ConnectionStatus;
  lastRefresh: string | null;
  scrapeCount: number;
  cardCount: number;
  targetAmount: number;
  scraperState: ScraperState;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
  autoBuyToggle?: React.ReactNode;
}

export default function StatusPanel({
  connectionStatus,
  lastRefresh,
  scrapeCount,
  cardCount,
  targetAmount,
  scraperState,
  onPause,
  onResume,
  onRestart,
  autoBuyToggle,
}: StatusPanelProps) {
  const statusColor =
    connectionStatus === "connected"
      ? "#22c55e"
      : connectionStatus === "connecting"
        ? "#eab308"
        : "#ef4444";

  const statusLabel =
    connectionStatus === "connected"
      ? "Connected"
      : connectionStatus === "connecting"
        ? "Connecting..."
        : "Disconnected";

  const isPaused = scraperState === "paused";
  const isRestarting = scraperState === "restarting";
  const isError = scraperState === "error";

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <View style={[styles.dot, { backgroundColor: statusColor }]} />
        <Text style={styles.statusText}>{statusLabel}</Text>
        {isError && <Text style={styles.errorBadge}>Error</Text>}
      </View>
      <View style={styles.metricsRow}>
        <View style={styles.metric}>
          <Text style={styles.metricValue}>{scrapeCount}</Text>
          <Text style={styles.metricLabel}>Scrapes</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricValue}>{cardCount}</Text>
          <Text style={styles.metricLabel}>Cards</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricValue}>${targetAmount}</Text>
          <Text style={styles.metricLabel}>Target</Text>
        </View>
      </View>
      <View style={styles.controlsRow}>
        {isPaused ? (
          <Pressable style={styles.controlBtn} onPress={onResume}>
            <Text style={styles.controlText}>▶️ Resume</Text>
          </Pressable>
        ) : (
          <Pressable
            style={[styles.controlBtn, isRestarting && styles.controlBtnDisabled]}
            onPress={onPause}
            disabled={isRestarting}
          >
            <Text style={styles.controlText}>⏸️ Pause</Text>
          </Pressable>
        )}
        <Pressable
          style={[styles.controlBtn, isRestarting && styles.controlBtnDisabled]}
          onPress={onRestart}
          disabled={isRestarting}
        >
          <Text style={styles.controlText}>
            {isRestarting ? "🔄 Restarting..." : "🔄 Restart"}
          </Text>
        </Pressable>
        {autoBuyToggle}
      </View>
      {lastRefresh && (
        <Text style={styles.label}>
          Last refresh: {lastRefresh}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  statusText: {
    color: "#f1f5f9",
    fontSize: 16,
    fontWeight: "600",
  },
  metricsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginBottom: 8,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: "#334155",
  },
  metric: {
    alignItems: "center",
  },
  metricValue: {
    color: "#22c55e",
    fontSize: 20,
    fontWeight: "700",
  },
  metricLabel: {
    color: "#94a3b8",
    fontSize: 11,
    marginTop: 2,
    textTransform: "uppercase",
  },
  label: {
    color: "#94a3b8",
    fontSize: 13,
    marginTop: 2,
  },
  controlsRow: {
    flexDirection: "row",
    justifyContent: "center",
    gap: 12,
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: "#334155",
  },
  controlBtn: {
    backgroundColor: "#334155",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  controlBtnDisabled: {
    opacity: 0.5,
  },
  controlText: {
    color: "#f1f5f9",
    fontSize: 14,
    fontWeight: "600",
  },
  errorBadge: {
    backgroundColor: "#ef4444",
    color: "#fff",
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: 8,
    textTransform: "uppercase",
  },
});
