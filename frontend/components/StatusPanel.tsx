import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { ConnectionStatus } from "../hooks/useSocket";

interface StatusPanelProps {
  connectionStatus: ConnectionStatus;
  lastRefresh: string | null;
  totalRefreshes?: number;
}

export default function StatusPanel({
  connectionStatus,
  lastRefresh,
  totalRefreshes,
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
      {lastRefresh && (
        <Text style={styles.label}>
          Last refresh: {lastRefresh}
        </Text>
      )}
      {totalRefreshes !== undefined && (
        <Text style={styles.label}>
          Total refreshes: {totalRefreshes}
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
    marginBottom: 8,
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
  label: {
    color: "#94a3b8",
    fontSize: 13,
    marginTop: 2,
  },
});
