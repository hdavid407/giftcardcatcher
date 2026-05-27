import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";

interface AutoBuyToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}

export default function AutoBuyToggle({ enabled, onToggle }: AutoBuyToggleProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>🤖 Auto-Buy</Text>
      <TouchableOpacity
        style={[styles.toggle, enabled ? styles.toggleOn : styles.toggleOff]}
        onPress={() => onToggle(!enabled)}
        activeOpacity={0.7}
      >
        <View style={[styles.thumb, enabled ? styles.thumbOn : styles.thumbOff]} />
      </TouchableOpacity>
      <Text style={[styles.status, enabled ? styles.statusOn : styles.statusOff]}>
        {enabled ? "ON" : "OFF"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 8,
  },
  label: {
    color: "#94a3b8",
    fontSize: 12,
    fontWeight: "600",
  },
  toggle: {
    width: 44,
    height: 24,
    borderRadius: 12,
    padding: 2,
    justifyContent: "center",
  },
  toggleOn: {
    backgroundColor: "#22c55e",
  },
  toggleOff: {
    backgroundColor: "#475569",
  },
  thumb: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "#ffffff",
  },
  thumbOn: {
    alignSelf: "flex-end",
  },
  thumbOff: {
    alignSelf: "flex-start",
  },
  status: {
    fontSize: 11,
    fontWeight: "700",
    width: 28,
  },
  statusOn: {
    color: "#22c55e",
  },
  statusOff: {
    color: "#64748b",
  },
});
