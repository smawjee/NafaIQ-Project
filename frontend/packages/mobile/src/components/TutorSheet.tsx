// Shared AI-tutor chat sheet (bottom modal). Used by the Learn hub and the
// lesson-detail screen; calls the ask-tutor Supabase Edge Function.
import { useRef, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";

import { TutorMessage as TutorBubble } from "@/components/ai/AiText";
import { Text } from "@/components/ui";
import { colors } from "@/constants/theme";
import { askTutor, type TutorMessage } from "@/lib/ai-tutor";
import { Bot, Send, Sparkles, X } from "@/lib/icons";

export function TutorSheet({
  visible,
  onClose,
  lessonTitle,
  section,
  presets = [],
  greeting = "Hi! I'm your NafaIQ tutor. Ask me anything.",
}: {
  visible: boolean;
  onClose: () => void;
  lessonTitle: string;
  section?: string;
  presets?: string[];
  greeting?: string;
}) {
  const [messages, setMessages] = useState<TutorMessage[]>([{ role: "assistant", content: greeting }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    const history: TutorMessage[] = [...messages, { role: "user", content: trimmed }];
    setMessages(history);
    setInput("");
    setLoading(true);
    const reply = await askTutor({ lessonTitle, section, messages: history.slice(-12) });
    setMessages((m) => [...m, { role: "assistant", content: reply }]);
    setLoading(false);
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.wrap}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close" />
        <View style={styles.sheet}>
          <View style={styles.header}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Bot color={colors.bull} size={18} />
              <Text style={{ fontWeight: "700" }}>Ask AI Tutor</Text>
            </View>
            <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
              <X color={colors.textSecondary} size={22} />
            </Pressable>
          </View>

          <ScrollView
            ref={scrollRef}
            style={{ flex: 1 }}
            contentContainerStyle={{ padding: 12, gap: 10 }}
            onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
          >
            {messages.map((m, i) => (
              <View key={i} style={[styles.bubble, m.role === "user" ? styles.user : styles.ai]}>
                <TutorBubble
                  content={m.content}
                  role={m.role}
                  color={m.role === "user" ? colors.bullForeground : colors.textPrimary}
                />
              </View>
            ))}
            {messages.length === 1 && presets.length > 0 && (
              <View style={{ gap: 6, paddingTop: 4 }}>
                {presets.map((p) => (
                  <Pressable key={p} onPress={() => send(p)} style={styles.preset} accessibilityRole="button">
                    <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{p}</Text>
                  </Pressable>
                ))}
              </View>
            )}
            {loading && (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <Sparkles color={colors.bull} size={14} />
                <Text variant="muted">Thinking…</Text>
              </View>
            )}
          </ScrollView>

          <View style={styles.inputBar}>
            <TextInput
              value={input}
              onChangeText={setInput}
              placeholder="Ask a question…"
              placeholderTextColor={colors.textMuted}
              style={styles.input}
              onSubmitEditing={() => send(input)}
              accessibilityLabel="Message the tutor"
            />
            <Pressable onPress={() => send(input)} disabled={loading} style={styles.sendBtn} accessibilityRole="button" accessibilityLabel="Send">
              {loading ? <ActivityIndicator color={colors.bullForeground} /> : <Send color={colors.bullForeground} size={16} />}
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: { height: "80%", backgroundColor: colors.sidebar, borderTopLeftRadius: 16, borderTopRightRadius: 16, borderTopWidth: 1, borderColor: colors.border },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  bubble: { maxWidth: "88%", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8 },
  user: { alignSelf: "flex-end", backgroundColor: colors.bull, borderBottomRightRadius: 2 },
  ai: { alignSelf: "flex-start", backgroundColor: colors.elevated, borderBottomLeftRadius: 2 },
  preset: { borderWidth: 1, borderColor: colors.border, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8 },
  inputBar: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: colors.border },
  input: { flex: 1, minHeight: 40, borderWidth: 1, borderColor: colors.border, borderRadius: 8, paddingHorizontal: 12, color: colors.textPrimary, backgroundColor: colors.elevated },
  sendBtn: { width: 40, height: 40, borderRadius: 8, backgroundColor: colors.bull, alignItems: "center", justifyContent: "center" },
});
