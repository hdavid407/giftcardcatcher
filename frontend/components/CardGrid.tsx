import React, { useState } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { CardInfo, CardStatus } from "../hooks/useSocket";

interface CardGridProps {
  cards: CardInfo[];
  cardStatuses: Map<number, CardStatus>;
  onBuyCard: (rowIndex: number) => void;
}

export default function CardGrid({ cards, cardStatuses, onBuyCard }: CardGridProps) {
  const [buyingRow, setBuyingRow] = useState<number | null>(null);

  if (cards.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No cards yet — waiting for first refresh...</Text>
      </View>
    );
  }

  const handleBuy = (item: CardInfo) => {
    setBuyingRow(item.button_row);
    onBuyCard(item.button_row);
  };

  const renderItem = ({ item }: { item: CardInfo }) => {
    const status = cardStatuses.get(item.card_number);
    const statusEmoji = status
      ? status.status === "unregistered"
        ? "🟢"
        : status.status === "registered"
        ? "🔴"
        : "⚪"
      : item.is_match
      ? "⏳"
      : null;

    return (
      <View style={[styles.row, item.is_match && styles.matchRow]}>
        <Text style={styles.cellNumber}>#{item.card_number}</Text>
        <Text style={styles.cellBin}>{item.bin}</Text>
        <Text style={styles.cellAmount}>
          {item.currency} ${item.amount.toFixed(2)}
        </Text>
        <Text style={styles.cellDiscount}>
          {item.discount ? `${item.discount}%` : "—"}
        </Text>
        <View style={styles.cellStatus}>
          <Text style={styles.statusEmoji}>{statusEmoji || "—"}</Text>
        </View>
        <View style={styles.cellBuy}>
          {item.is_match ? (
            <TouchableOpacity
              style={[
                styles.buyButton,
                buyingRow === item.button_row && styles.buyButtonDisabled,
              ]}
              onPress={() => handleBuy(item)}
              disabled={buyingRow === item.button_row}
            >
              <Text style={styles.buyButtonText}>
                {buyingRow === item.button_row ? "…" : "💰"}
              </Text>
            </TouchableOpacity>
          ) : (
            <Text style={styles.cellBuyPlaceholder}>—</Text>
          )}
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Live Card Grid ({cards.length} cards)</Text>
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>#</Text>
        <Text style={[styles.headerCell, { flex: 1.5 }]}>BIN</Text>
        <Text style={[styles.headerCell, { flex: 1.8 }]}>Amount</Text>
        <Text style={[styles.headerCell, { flex: 0.8 }]}>Disc</Text>
        <Text style={[styles.headerCell, { flex: 0.7 }]}>Sts</Text>
        <Text style={[styles.headerCell, { flex: 0.7 }]}>Buy</Text>
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
  cellStatus: {
    flex: 0.7,
    alignItems: "center",
  },
  statusEmoji: {
    fontSize: 12,
  },
  cellBuy: {
    flex: 0.7,
    alignItems: "center",
  },
  buyButton: {
    backgroundColor: "#22c55e",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  buyButtonDisabled: {
    backgroundColor: "#4b5563",
  },
  buyButtonText: {
    color: "#fff",
    fontSize: 14,
  },
  cellBuyPlaceholder: {
    color: "#4b5563",
    fontSize: 12,
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
