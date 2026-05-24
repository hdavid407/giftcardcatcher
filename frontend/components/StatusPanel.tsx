import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { ConnectionStatus } from "../hooks/useSocket";

interface StatusPanelProps {
  connectionStatus: ConnectionStatus;
  lastRefresh: string | null;
  scrapeCount: number;
  cardCount: number;
  targetAmount: number;
}

export default function StatusPanel({
  connectionStatus,
  lastRefresh,
  scrapeCount,
  cardCount,
  targetAmount,
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

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <View style={[styles.dot, { backgroundColor: statusColor }]} />
        <Text style={styles.statusText}>{statusLabel}</Text>
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
});
