// NafaIQ Assistant (`/assistant`) — the voice+text agent, opened from the
// account menu. Mirrors web features/assistant/AssistantPanel.tsx as a
// full-screen liquid-glass chat: streaming answers, action-draft confirmation
// cards, presets, quota banner, and mic input. Chat layout follows
// TutorSheet.tsx; the screen owns its own header (more.tsx pattern) because
// the composer must sit inside a flexing KeyboardAvoidingView.
import { useRouter } from "expo-router";
import { useMemo, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import Animated, { FadeInDown, FadeOut } from "react-native-reanimated";
import { SafeAreaView } from "react-native-safe-area-context";

import { TutorMessage as Bubble } from "@/components/ai/AiText";
import { ActionDraftCard } from "@/components/assistant/ActionDraftCard";
import { AssistantMicButton } from "@/components/assistant/AssistantMicButton";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useAssistantChat } from "@/hooks/ai/use-assistant-chat";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { ArrowLeft, Bot, LogIn, Send, Sparkles } from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

// Chosen to advertise capability breadth: one write, one read, one alert. A
// user who only ever sees a chat box assumes it only chats. (Web parity.)
const PRESETS = [
  "Add transaction of 1200 for food via Meezan card",
  "How much did I spend this month?",
  "Alert me when any goal reaches 50%",
  "Add MEBL to my watchlist",
];

export default function AssistantScreen() {
  const { t, isUrdu } = useLang();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();

  const [toast, setToast] = useState<{ message: string; kind: "success" | "error" } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function showToast(message: string, kind: "success" | "error" = "success") {
    setToast({ message, kind });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2600);
  }

  const {
    messages,
    loading,
    quotaExceeded,
    signedOut,
    pending,
    busyAction,
    send,
    confirmPending,
    cancelPending,
  } = useAssistantChat(
    t(
      "Hi! I can add transactions, track bills and goals, manage your portfolio and watchlist, and answer questions about your money. Type or tap the mic.",
    ),
    { onToast: showToast },
  );

  const [input, setInput] = useState("");
  const scrollRef = useRef<ScrollView>(null);

  const submit = (text: string) => {
    send(text);
    setInput("");
  };

  const showPresets = messages.length === 1 && !signedOut;
  const composerDisabled = quotaExceeded || loading;

  return (
    <GlassScreen>
      <SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right"]}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          {/* Header */}
          <View style={styles.header}>
            <Pressable
              onPress={() => router.back()}
              hitSlop={12}
              style={styles.backBtn}
              accessibilityRole="button"
              accessibilityLabel={t("Go back")}
            >
              <ArrowLeft color={colors.textPrimary} size={22} />
            </Pressable>
            <Bot color={colors.bull} size={20} />
            <Text variant="display" style={{ fontFamily: AVENIR, fontSize: 22 }}>
              {t("NafaIQ Assistant")}
            </Text>
            <View style={styles.aiBadge}>
              <Text style={{ color: colors.ai, fontSize: 9, fontWeight: "700" }}>
                {t("Powered by AI")}
              </Text>
            </View>
          </View>

          {/* Conversation */}
          <ScrollView
            ref={scrollRef}
            style={{ flex: 1 }}
            contentContainerStyle={styles.thread}
            keyboardShouldPersistTaps="handled"
            onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
          >
            {messages.map((m, i) => (
              <View key={i} style={[styles.bubble, m.role === "user" ? styles.user : styles.ai]}>
                <Bubble
                  content={m.content}
                  role={m.role}
                  color={m.role === "user" ? colors.bullForeground : colors.textPrimary}
                />
              </View>
            ))}

            {showPresets && (
              <View style={{ gap: 6, paddingTop: 4 }}>
                {PRESETS.map((p) => (
                  <Pressable
                    key={p}
                    onPress={() => submit(t(p))}
                    style={styles.preset}
                    accessibilityRole="button"
                    accessibilityLabel={t(p)}
                  >
                    <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{t(p)}</Text>
                  </Pressable>
                ))}
              </View>
            )}

            {pending && (
              <ActionDraftCard
                // Remount on a new draft so the card's field state is seeded
                // from it rather than retaining the previous draft's edits.
                key={`${pending.action}-${messages.length}`}
                draft={pending}
                busy={busyAction}
                onConfirm={(args) => void confirmPending(args)}
                onCancel={cancelPending}
              />
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
                  {t("Daily assistant limit reached — it resets tomorrow.")}
                </Text>
              </View>
            )}
          </ScrollView>

          {/* Composer */}
          {signedOut ? (
            <View style={styles.signedOut}>
              <Pressable
                onPress={() => router.push("/auth")}
                style={styles.signInBtn}
                accessibilityRole="button"
                accessibilityLabel={t("Sign in to use NafaIQ Assistant")}
              >
                <LogIn color={colors.bullForeground} size={16} />
                <Text style={{ color: colors.bullForeground, fontWeight: "700", fontSize: 13 }}>
                  {t("Sign in to use NafaIQ Assistant")}
                </Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.inputBar}>
              <AssistantMicButton
                disabled={composerDisabled}
                // Lands in the input, never auto-sent: the user confirms what
                // was heard before anything acts on it.
                onTranscript={(text) => setInput((current) => (current ? `${current} ${text}` : text))}
                onError={(message) => showToast(message, "error")}
              />
              <TextInput
                value={input}
                onChangeText={setInput}
                placeholder={t("Ask or tell me what to do…")}
                placeholderTextColor={colors.textMuted}
                style={[styles.input, composerDisabled && { opacity: 0.5 }]}
                editable={!composerDisabled}
                onSubmitEditing={() => submit(input)}
                accessibilityLabel={t("Message the assistant")}
              />
              <Pressable
                onPress={() => submit(input)}
                disabled={composerDisabled}
                style={[styles.sendBtn, composerDisabled && { opacity: 0.5 }]}
                accessibilityRole="button"
                accessibilityLabel={t("Send")}
              >
                <Send color={colors.bullForeground} size={16} />
              </Pressable>
            </View>
          )}

          {/* Toast */}
          {toast && (
            <Animated.View
              entering={FadeInDown}
              exiting={FadeOut}
              style={styles.toastWrap}
              pointerEvents="none"
            >
              <GlassCard radius={999} intensity={40} style={styles.toast}>
                <Text
                  style={{
                    fontWeight: "600",
                    fontSize: 13,
                    color: toast.kind === "error" ? colors.bear : colors.textPrimary,
                  }}
                >
                  {toast.message}
                </Text>
              </GlassCard>
            </Animated.View>
          )}
        </KeyboardAvoidingView>
      </SafeAreaView>
    </GlassScreen>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: c.border,
    },
    backBtn: { minWidth: 40, minHeight: 40, alignItems: "center", justifyContent: "center", marginLeft: -10 },
    aiBadge: { backgroundColor: c.ai + "26", borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
    thread: { padding: 16, gap: 10, paddingBottom: 20 },
    bubble: { maxWidth: "88%", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8 },
    user: { alignSelf: "flex-end", backgroundColor: c.bull, borderBottomRightRadius: 2 },
    ai: { alignSelf: "flex-start", backgroundColor: c.glassFill, borderBottomLeftRadius: 2 },
    preset: {
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.glassFill,
      borderRadius: 999,
      paddingHorizontal: 12,
      paddingVertical: 8,
      minHeight: 44,
      justifyContent: "center",
    },
    quota: {
      borderWidth: 1,
      borderColor: c.warning + "66",
      backgroundColor: c.warning + "1a",
      borderRadius: 8,
      paddingHorizontal: 12,
      paddingVertical: 8,
    },
    quotaText: { color: c.warning, fontSize: 12 },
    signedOut: { padding: 12, borderTopWidth: 1, borderTopColor: c.border, alignItems: "center" },
    signInBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      backgroundColor: c.bull,
      borderRadius: 8,
      paddingHorizontal: 16,
      minHeight: 44,
    },
    inputBar: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      padding: 12,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: c.border,
    },
    input: {
      flex: 1,
      minHeight: 44,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      paddingHorizontal: 12,
      color: c.textPrimary,
      backgroundColor: c.glassFill,
    },
    sendBtn: {
      width: 44,
      height: 44,
      borderRadius: 8,
      backgroundColor: c.bull,
      alignItems: "center",
      justifyContent: "center",
    },
    toastWrap: { position: "absolute", left: 0, right: 0, bottom: 84, alignItems: "center" },
    toast: { paddingHorizontal: 16, paddingVertical: 10, flexDirection: "row", alignItems: "center", gap: 6 },
  });
