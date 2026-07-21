// Shared AI-tutor chat sheet (bottom modal). Used by the lesson-detail screen.
// Streams tokens from the FastAPI /api/ai/tutor SSE endpoint via useTutorChat —
// quota banner, signed-out CTA, abort on close. (Replaces the legacy ask-tutor
// Supabase Edge Function.)
import { BlurView } from "expo-blur";
import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";

import { TutorMessage as TutorBubble } from "@/components/ai/AiText";
import { Text } from "@/components/ui";
import { colors, fonts } from "@/constants/theme";
import { useTutorChat } from "@/hooks/ai/use-tutor-chat";
import { useLang } from "@/hooks/use-lang";
import { Bot, LogIn, Send, Sparkles, X } from "@/lib/icons";

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
  const { t, isUrdu } = useLang();
  const router = useRouter();
  const { messages, loading, quotaExceeded, signedOut, send, abort } = useTutorChat({
    lessonTitle,
    lessonContext: section,
    greeting,
  });
  const [input, setInput] = useState("");
  const scrollRef = useRef<ScrollView>(null);

  // Abort any in-flight stream when the sheet is dismissed.
  const close = () => {
    abort();
    onClose();
  };

  useEffect(() => {
    if (!visible) abort();
  }, [visible, abort]);

  const submit = (text: string) => {
    send(text);
    setInput("");
  };

  const showPresets = messages.length === 1 && !signedOut && presets.length > 0;
  const disabled = loading || quotaExceeded;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={close}>
      <KeyboardAvoidingView style={styles.wrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <Pressable style={StyleSheet.absoluteFill} onPress={close} accessibilityRole="button" accessibilityLabel={t("Close")} />
        <View style={styles.sheet}>
          <BlurView tint="dark" intensity={40} experimentalBlurMethod="dimezisBlurView" style={StyleSheet.absoluteFill} />
          <View style={styles.header}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Bot color={colors.bull} size={18} />
              <Text style={{ fontWeight: "700" }}>{t("Ask AI Tutor")}</Text>
              <View style={styles.aiBadge}>
                <Text style={{ color: colors.ai, fontSize: 9, fontWeight: "700" }}>{t("Powered by AI")}</Text>
              </View>
            </View>
            <Pressable onPress={close} hitSlop={8} accessibilityRole="button" accessibilityLabel={t("Close")}>
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
            {showPresets && (
              <View style={{ gap: 6, paddingTop: 4 }}>
                {presets.map((p) => (
                  <Pressable key={p} onPress={() => submit(p)} style={styles.preset} accessibilityRole="button" accessibilityLabel={t(p)}>
                    <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{t(p)}</Text>
                  </Pressable>
                ))}
              </View>
            )}
            {loading && (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <Sparkles color={colors.bull} size={14} />
                <Text variant="muted">{t("Thinking…")}</Text>
              </View>
            )}
            {quotaExceeded && (
              <View style={styles.quota}>
                <Text style={[styles.quotaText, isUrdu && { fontFamily: fonts.urdu }]}>
                  {t("Daily tutor limit reached — upgrade your plan or come back tomorrow.")}
                </Text>
              </View>
            )}
          </ScrollView>

          {signedOut ? (
            <View style={styles.signedOut}>
              <Pressable
                onPress={() => {
                  close();
                  router.push("/auth");
                }}
                style={styles.signInBtn}
                accessibilityRole="button"
                accessibilityLabel={t("Sign in to chat with your tutor")}
              >
                <LogIn color={colors.bullForeground} size={16} />
                <Text style={{ color: colors.bullForeground, fontWeight: "700", fontSize: 13 }}>
                  {t("Sign in to chat with your tutor")}
                </Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.inputBar}>
              <TextInput
                value={input}
                onChangeText={setInput}
                placeholder={t("Ask about this lesson…")}
                placeholderTextColor={colors.textMuted}
                style={[styles.input, disabled && { opacity: 0.5 }]}
                editable={!disabled}
                onSubmitEditing={() => submit(input)}
                accessibilityLabel={t("Message the tutor")}
              />
              <Pressable
                onPress={() => submit(input)}
                disabled={disabled}
                style={[styles.sendBtn, disabled && { opacity: 0.5 }]}
                accessibilityRole="button"
                accessibilityLabel={t("Send")}
              >
                <Send color={colors.bullForeground} size={16} />
              </Pressable>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: { height: "80%", backgroundColor: "rgba(10,16,30,0.72)", borderTopLeftRadius: 16, borderTopRightRadius: 16, borderTopWidth: 1, borderColor: colors.border, overflow: "hidden" },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  aiBadge: { backgroundColor: colors.ai + "26", borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  bubble: { maxWidth: "88%", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8 },
  user: { alignSelf: "flex-end", backgroundColor: colors.bull, borderBottomRightRadius: 2 },
  ai: { alignSelf: "flex-start", backgroundColor: colors.glassFill, borderBottomLeftRadius: 2 },
  preset: { borderWidth: 1, borderColor: colors.border, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8, minHeight: 44, justifyContent: "center" },
  quota: { borderWidth: 1, borderColor: colors.warning + "66", backgroundColor: colors.warning + "1a", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  quotaText: { color: colors.warning, fontSize: 12 },
  signedOut: { padding: 12, borderTopWidth: 1, borderTopColor: colors.border, alignItems: "center" },
  signInBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: colors.bull, borderRadius: 8, paddingHorizontal: 16, minHeight: 44 },
  inputBar: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: colors.border },
  input: { flex: 1, minHeight: 44, borderWidth: 1, borderColor: colors.border, borderRadius: 8, paddingHorizontal: 12, color: colors.textPrimary, backgroundColor: colors.glassFill },
  sendBtn: { width: 44, height: 44, borderRadius: 8, backgroundColor: colors.bull, alignItems: "center", justifyContent: "center" },
});
