import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Vibration,
} from "react-native";
import { MatchData, approveMatch, denyMatch } from "../api/client";

interface MatchAlertProps {
  match: MatchData;
  onApproved: () => void;
  onDenied: () => void;
  onExpired: () => void;
}

export default function MatchAlert({
  match,
  onApproved,
  onDenied,
  onExpired,
}: MatchAlertProps) {
  const [remaining, setRemaining] = useState(match.remaining_seconds);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  // Vibrate on mount
  useEffect(() => {
    try {
      Vibration.vibrate([0, 200, 100, 200]);
    } catch {}
  }, []);

  // Pulse animation
  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.05,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  // Countdown timer
  useEffect(() => {
    const interval = setInterval(() => {
      setRemaining((prev) => {
        const next = prev - 1;
        if (next <= 0) {
          clearInterval(interval);
          onExpired();
          return 0;
        }
        return next;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [onExpired]);

  const handleApprove = async () => {
    setActionLoading("approve");
    try {
      await approveMatch();
      onApproved();
    } catch (err) {
      console.error("Approve failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeny = async () => {
    setActionLoading("deny");
    try {
      await denyMatch();
      onDenied();
    } catch (err) {
      console.error("Deny failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const timerColor = remaining < 30 ? "#ef4444" : remaining < 60 ? "#eab308" : "#22c55e";

  return (
    <View style={styles.overlay}>
      <Animated.View
        style={[styles.card, { transform: [{ scale: pulseAnim }] }]}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.icon}>🎯</Text>
          <Text style={styles.title}>Gift Card Found!</Text>
        </View>

        {/* Card details */}
        <Text style={styles.cardText}>{match.card_text}</Text>
        {match.price && <Text style={styles.price}>Price: {match.price}</Text>}

        {/* Countdown */}
        <View style={styles.timerContainer}>
          <Text style={[styles.timer, { color: timerColor }]}>
            {minutes}:{seconds.toString().padStart(2, "0")}
          </Text>
          <Text style={styles.timerLabel}>remaining</Text>
        </View>

        {/* Actions */}
        <View style={styles.actions}>
          <TouchableOpacity
            style={[styles.button, styles.buyButton]}
            onPress={handleApprove}
            disabled={actionLoading !== null}
          >
            <Text style={styles.buttonText}>
              {actionLoading === "approve" ? "Buying..." : "💰 Buy Now"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.button, styles.skipButton]}
            onPress={handleDeny}
            disabled={actionLoading !== null}
          >
            <Text style={styles.buttonText}>
              {actionLoading === "deny" ? "Skipping..." : "✕ Skip"}
            </Text>
          </TouchableOpacity>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0, 0, 0, 0.85)",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 100,
  },
  card: {
    backgroundColor: "#1e293b",
    borderRadius: 20,
    padding: 28,
    width: "90%",
    maxWidth: 400,
    borderWidth: 2,
    borderColor: "#22c55e",
    alignItems: "center",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  icon: {
    fontSize: 28,
    marginRight: 8,
  },
  title: {
    color: "#22c55e",
    fontSize: 24,
    fontWeight: "700",
  },
  cardText: {
    color: "#f1f5f9",
    fontSize: 18,
    textAlign: "center",
    marginBottom: 8,
    fontWeight: "600",
  },
  price: {
    color: "#94a3b8",
    fontSize: 16,
    marginBottom: 16,
  },
  timerContainer: {
    alignItems: "center",
    marginBottom: 24,
  },
  timer: {
    fontSize: 48,
    fontWeight: "700",
    fontVariant: ["tabular-nums"],
  },
  timerLabel: {
    color: "#64748b",
    fontSize: 14,
    marginTop: -4,
  },
  actions: {
    flexDirection: "row",
    gap: 12,
    width: "100%",
  },
  button: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  buyButton: {
    backgroundColor: "#22c55e",
  },
  skipButton: {
    backgroundColor: "#334155",
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
  },
});
