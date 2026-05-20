import React, { useCallback, useState } from "react";
import { View, Text, StyleSheet, SafeAreaView } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSocket } from "./hooks/useSocket";
import StatusPanel from "./components/StatusPanel";
import LogStream from "./components/LogStream";
import MatchAlert from "./components/MatchAlert";

export default function App() {
  const { status, match, logs, lastRefresh, resetMatch } = useSocket();
  const [totalRefreshes] = useState(0);

  const handleApproved = useCallback(() => {
    resetMatch();
  }, [resetMatch]);

  const handleDenied = useCallback(() => {
    resetMatch();
  }, [resetMatch]);

  const handleExpired = useCallback(() => {
    resetMatch();
  }, [resetMatch]);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Gift Card Monitor</Text>
        <Text style={styles.subtitle}>Watching for $50 GiftCardMall</Text>
      </View>

      {/* Status */}
      <StatusPanel
        connectionStatus={status}
        lastRefresh={lastRefresh}
        totalRefreshes={totalRefreshes}
      />

      {/* Log Stream */}
      <LogStream logs={logs} />

      {/* Match Alert Overlay */}
      {match && (
        <MatchAlert
          match={match}
          onApproved={handleApproved}
          onDenied={handleDenied}
          onExpired={handleExpired}
        />
      )}
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
    marginBottom: 16,
  },
  title: {
    color: "#f1f5f9",
    fontSize: 28,
    fontWeight: "800",
  },
  subtitle: {
    color: "#64748b",
    fontSize: 14,
    marginTop: 2,
  },
});
