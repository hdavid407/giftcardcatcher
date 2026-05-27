import React, { useCallback, useState } from "react";
import { View, Text, StyleSheet, SafeAreaView, ScrollView } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSocket } from "./hooks/useSocket";
import StatusPanel from "./components/StatusPanel";
import LogStream from "./components/LogStream";
import CardGrid from "./components/CardGrid";
import SettingsPanel from "./components/SettingsPanel";

export default function App() {
  const { status, logs, lastRefresh, cards, verifiedCards, scrapeCount, targetAmount, scraperState, sendControl, sendPurchase } = useSocket();
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
        <CardGrid cards={cards} verifiedCards={verifiedCards} onBuyCard={handleBuyCard} />

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
