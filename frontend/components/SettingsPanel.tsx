import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import apiClient from "../api/client";

interface SettingsPanelProps {
  currentAmount: number;
  onAmountChanged: (amount: number) => void;
}

export default function SettingsPanel({
  currentAmount,
  onAmountChanged,
}: SettingsPanelProps) {
  const [inputValue, setInputValue] = useState(currentAmount.toString());
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    const amount = parseFloat(inputValue);
    if (isNaN(amount) || amount <= 0) {
      return;
    }

    setSaving(true);
    try {
      await apiClient.post("/api/target_amount", { amount });
      onAmountChanged(amount);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error("Failed to update target amount:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.header}>⚙️ Settings</Text>

      <View style={styles.row}>
        <Text style={styles.label}>Target Amount ($)</Text>
        <TextInput
          style={styles.input}
          value={inputValue}
          onChangeText={setInputValue}
          keyboardType="decimal-pad"
          placeholder="50"
          placeholderTextColor="#64748b"
        />
        <TouchableOpacity
          style={[styles.button, saving && styles.buttonDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          <Text style={styles.buttonText}>
            {saving ? "Saving..." : saved ? "Saved ✓" : "Save"}
          </Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.hint}>
        The bot will watch for unregistered cards at this amount.
      </Text>
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
  header: {
    color: "#f1f5f9",
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 12,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  label: {
    color: "#94a3b8",
    fontSize: 14,
    marginRight: 8,
  },
  input: {
    backgroundColor: "#0f172a",
    color: "#f1f5f9",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 16,
    width: 80,
    textAlign: "center",
    borderWidth: 1,
    borderColor: "#334155",
  },
  button: {
    backgroundColor: "#22c55e",
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
  hint: {
    color: "#64748b",
    fontSize: 12,
    marginTop: 8,
  },
});
