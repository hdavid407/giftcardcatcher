import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
} from "react-native";
import { PurchasePreview, PurchaseComplete } from "../hooks/useSocket";

interface PurchaseModalProps {
  preview: PurchasePreview | null;
  complete: PurchaseComplete | null;
  onConfirm: (rowIndex: number) => void;
  onCancel: (rowIndex: number) => void;
}

export default function PurchaseModal({
  preview,
  complete,
  onConfirm,
  onCancel,
}: PurchaseModalProps) {
  if (!preview) {
    return null;
  }

  const statusEmoji =
    preview.status === "unregistered"
      ? "🟢"
      : preview.status === "registered"
      ? "🔴"
      : "⚪";

  return (
    <Modal
      animationType="slide"
      transparent={true}
      visible={!!preview}
      onRequestClose={() => onCancel(preview.button_row)}
    >
      <View style={styles.overlay}>
        <View style={styles.modal}>
          <Text style={styles.title}>Confirm Purchase</Text>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Card ID:</Text>
            <Text style={styles.detailValue}>{preview.id || "—"}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>BIN:</Text>
            <Text style={styles.detailValue}>{preview.bin || "—"}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Balance:</Text>
            <Text style={styles.detailValue}>
              {preview.currency} ${preview.balance?.toFixed(2) || "—"}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Price:</Text>
            <Text style={styles.detailValue}>
              {preview.currency} ${preview.price?.toFixed(2) || "—"}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Rate:</Text>
            <Text style={styles.detailValue}>
              {preview.rate ? `${preview.rate}%` : "—"}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Status:</Text>
            <Text style={styles.detailValue}>
              {statusEmoji} {preview.status}
            </Text>
          </View>

          {complete && (
            <Text
              style={[
                styles.resultText,
                complete.success ? styles.successText : styles.errorText,
              ]}
            >
              {complete.success
                ? "✅ Purchase successful!"
                : `❌ Purchase failed: ${complete.reason || "unknown"}`}
            </Text>
          )}

          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={[styles.button, styles.cancelButton]}
              onPress={() => onCancel(preview.button_row)}
              disabled={!!complete}
            >
              <Text style={styles.buttonText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.button, styles.confirmButton]}
              onPress={() => onConfirm(preview.button_row)}
              disabled={!!complete}
            >
              <Text style={styles.buttonText}>Confirm Purchase</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  modal: {
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 24,
    width: "100%",
    maxWidth: 400,
  },
  title: {
    color: "#f1f5f9",
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 16,
    textAlign: "center",
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  detailLabel: {
    color: "#94a3b8",
    fontSize: 14,
  },
  detailValue: {
    color: "#f1f5f9",
    fontSize: 14,
    fontWeight: "500",
  },
  resultText: {
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
    marginTop: 12,
    marginBottom: 4,
  },
  successText: {
    color: "#22c55e",
  },
  errorText: {
    color: "#ef4444",
  },
  buttonRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 20,
    gap: 12,
  },
  button: {
    flex: 1,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  cancelButton: {
    backgroundColor: "#475569",
  },
  confirmButton: {
    backgroundColor: "#22c55e",
  },
  buttonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
});
