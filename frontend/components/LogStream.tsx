import React, { useRef, useEffect } from "react";
import { View, Text, FlatList, StyleSheet } from "react-native";

interface LogStreamProps {
  logs: string[];
}

export default function LogStream({ logs }: LogStreamProps) {
  const listRef = useRef<FlatList>(null);

  useEffect(() => {
    if (logs.length > 0) {
      listRef.current?.scrollToOffset({ offset: 0, animated: true });
    }
  }, [logs.length]);

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Activity Log</Text>
      <FlatList
        ref={listRef}
        data={logs}
        keyExtractor={(_, i) => i.toString()}
        renderItem={({ item }) => (
          <Text style={styles.logItem}>{item}</Text>
        )}
        style={styles.list}
        contentContainerStyle={styles.listContent}
        inverted={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  header: {
    color: "#64748b",
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 8,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 8,
  },
  logItem: {
    color: "#94a3b8",
    fontSize: 12,
    fontFamily: "monospace",
    lineHeight: 18,
    paddingVertical: 1,
  },
});
