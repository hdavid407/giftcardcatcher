import React from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
} from "react-native";
import { CardInfo } from "../hooks/useSocket";

interface CardGridProps {
  cards: CardInfo[];
}

export default function CardGrid({ cards }: CardGridProps) {
  if (cards.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No cards yet — waiting for first refresh...</Text>
      </View>
    );
  }

  const renderItem = ({ item }: { item: CardInfo }) => (
    <View style={[styles.row, item.is_match && styles.matchRow]}>
      <Text style={styles.cellNumber}>#{item.card_number}</Text>
      <Text style={styles.cellBin}>{item.bin}</Text>
      <Text style={styles.cellAmount}>
        {item.currency} ${item.amount.toFixed(2)}
      </Text>
      <Text style={styles.cellDiscount}>
        {item.discount ? `${item.discount}%` : "—"}
      </Text>
      {item.is_match && <View style={styles.matchBadge}><Text style={styles.matchText}>🎯</Text></View>}
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Live Card Grid ({cards.length} cards)</Text>
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>#</Text>
        <Text style={[styles.headerCell, { flex: 1.5 }]}>BIN</Text>
        <Text style={[styles.headerCell, { flex: 1.8 }]}>Amount</Text>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>Disc</Text>
      </View>
      <FlatList
        data={cards}
        keyExtractor={(item) => item.card_number.toString()}
        renderItem={renderItem}
        style={styles.list}
        contentContainerStyle={styles.listContent}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    maxHeight: 300,
  },
  header: {
    color: "#64748b",
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 8,
  },
  headerRow: {
    flexDirection: "row",
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  headerCell: {
    color: "#94a3b8",
    fontSize: 11,
    fontWeight: "600",
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 8,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  matchRow: {
    backgroundColor: "rgba(34, 197, 94, 0.1)",
    borderLeftWidth: 3,
    borderLeftColor: "#22c55e",
  },
  cellNumber: {
    flex: 0.8,
    color: "#94a3b8",
    fontSize: 12,
  },
  cellBin: {
    flex: 1.5,
    color: "#f1f5f9",
    fontSize: 12,
    fontWeight: "500",
  },
  cellAmount: {
    flex: 1.8,
    color: "#f1f5f9",
    fontSize: 12,
  },
  cellDiscount: {
    flex: 0.8,
    color: "#eab308",
    fontSize: 12,
  },
  matchBadge: {
    marginLeft: 4,
  },
  matchText: {
    fontSize: 14,
  },
  empty: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 24,
    alignItems: "center",
    marginBottom: 12,
  },
  emptyText: {
    color: "#64748b",
    fontSize: 14,
  },
});
