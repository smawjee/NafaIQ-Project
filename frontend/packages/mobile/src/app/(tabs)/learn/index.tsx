// Learn Hub (`/learn/`). Mirrors web /learn/: hero + XP, learning paths, lessons
// grid, searchable glossary, flashcard mode, AI tutor chat sheet. Theme + i18n.
import { useRouter } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { BlurView } from "expo-blur";
import { SafeAreaView } from "react-native-safe-area-context";

import { TutorMessage as TutorBubble } from "@/components/ai/AiText";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Text } from "@/components/ui";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { fonts, radii, type ThemeColors } from "@/constants/theme";
import { useTutorChat } from "@/hooks/ai/use-tutor-chat";
import { useLearnSearch, type ApiLearnSearchResult } from "@/hooks/ai/use-learn-search";
import { useLang } from "@/hooks/use-lang";
import { useLearn, XP_GOAL } from "@/hooks/use-learn";
import { useTheme } from "@/hooks/use-theme";
import { FLASHCARDS, GLOSSARY, LEARNING_PATHS, LESSON_ID_BY_TITLE, LESSONS, VIDEO_LESSON_IDS } from "@nafaiq/shared";
import {
  ArrowRight,
  Bot,
  Check,
  Flame,
  iconFor,
  Layers,
  LogIn,
  PartyPopper,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  Star,
  Target,
  Trophy,
  Video,
  X,
} from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

export default function LearnHub() {
  const { xp, statusOf, pathProgress } = useLearn();
  const { colors } = useTheme();
  const { t } = useLang();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [openTerm, setOpenTerm] = useState<string | null>(null);
  const [flashOpen, setFlashOpen] = useState(false);
  const [tutorOpen, setTutorOpen] = useState(false);

  const lessonsDone = useMemo(
    () => LESSONS.filter((l) => statusOf(LESSON_ID_BY_TITLE[l.title]) === "complete").length,
    [statusOf],
  );
  const lessonsInProgress = useMemo(
    () => LESSONS.filter((l) => statusOf(LESSON_ID_BY_TITLE[l.title]) === "in-progress").length,
    [statusOf],
  );
  // Level derived from XP (real), replacing the old hardcoded "Beginner".
  const level = xp >= 400 ? "Advanced" : xp >= 150 ? "Intermediate" : "Beginner";
  const terms = GLOSSARY.filter((term) => term.en.toLowerCase().includes(search.toLowerCase()));

  return (
    <GlassScreen>
      <SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right"]}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text variant="display" style={{ fontFamily: AVENIR }}>{t("Learn Hub")}</Text>
        {/* Hero */}
        <GlassCard style={{ gap: 8, padding: 16, borderColor: colors.ai + "33" }}>
          <Text style={{ fontFamily: fonts.urdu, fontSize: 24, color: colors.textPrimary }} numberOfLines={1}>سمجھو، سیکھو، بڑھو</Text>
          <Text style={{ fontWeight: "700" }}>Samjho, Seekho, Barho</Text>
          <Text variant="secondary">{t("From KSE basics to technical analysis — in Urdu and English.")}</Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 4 }}>
            <View style={{ flex: 1 }}>
              <ProgressBar value={xp / XP_GOAL} color={colors.bull} />
            </View>
            <Text variant="mono" style={{ fontSize: 12 }}>{xp} / {XP_GOAL} XP</Text>
          </View>
          <View style={styles.chips}>
            <StatChip icon={<Flame color={colors.warning} size={13} />} label={`${lessonsInProgress} ${t("In progress")}`} color={colors.warning} />
            <StatChip icon={<Target color={colors.bull} size={13} />} label={`${lessonsDone} ${t("Done")}`} color={colors.bull} />
            <StatChip icon={<Star color={colors.gold} size={13} />} label={`${xp} XP`} color={colors.gold} />
            <StatChip icon={<Trophy color="#8b5cf6" size={13} />} label={t(level)} color="#8b5cf6" />
          </View>
        </GlassCard>

        {/* AI content search (RAG) — only renders when the backend flag is on */}
        <LearnSearchBox />

        {/* Learning Paths */}
        <Text variant="title">{t("Learning Paths")}</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
          {LEARNING_PATHS.map((p) => {
            const frac = pathProgress(p.lessonIds);
            const first = p.lessonIds.find((l) => statusOf(l) !== "complete") ?? p.lessonIds[0];
            const Icon = iconFor(p.emoji);
            return (
              <View key={p.id} style={[styles.pathCard, { borderLeftColor: p.accent }]}>
                <View style={styles.pathIcon}>
                  <Icon color={p.accent} size={18} />
                </View>
                <Text style={{ fontWeight: "700", marginTop: 6 }} numberOfLines={1}>{t(p.title)}</Text>
                <Text variant="muted" numberOfLines={2}>{t(p.description)}</Text>
                <Text variant="mono" style={{ fontSize: 11, marginTop: 4 }} numberOfLines={1}>{p.lessonIds.length} {t("lessons")} · {p.estMin} min</Text>
                <View style={{ marginTop: 8 }}>
                  <ProgressBar value={frac} color={p.accent} height={6} />
                </View>
                <Pressable onPress={() => router.push(`/(tabs)/learn/lesson/${first}`)} style={[styles.pathBtn, { backgroundColor: p.accent + "1a" }]} accessibilityRole="button">
                  <Text style={{ color: p.accent, fontWeight: "700", fontSize: 12 }}>{frac > 0 ? t("Continue Path") : t("Start Path")}</Text>
                  <ArrowRight color={p.accent} size={14} />
                </Pressable>
              </View>
            );
          })}
        </ScrollView>

        {/* Lessons */}
        <Text variant="title">{t("Lessons")}</Text>
        <View style={styles.grid}>
          {LESSONS.map((l) => {
            const id = LESSON_ID_BY_TITLE[l.title];
            const status = statusOf(id);
            const isVideo = VIDEO_LESSON_IDS.has(id);
            const Icon = iconFor(l.emoji);
            return (
              <Pressable key={l.title} style={styles.lessonCard} onPress={() => router.push(`/(tabs)/learn/lesson/${id}`)} accessibilityRole="button" accessibilityLabel={`${l.title}, ${status}`}>
                <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 10 }}>
                  <View style={styles.lessonIcon}>
                    <Icon color={colors.textSecondary} size={18} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontWeight: "600", fontSize: 13 }} numberOfLines={2}>{t(l.title)}</Text>
                    <Text variant="muted" style={{ marginTop: 2 }} numberOfLines={1}>{l.duration} · {t(l.level)}</Text>
                  </View>
                  <CompletionRing status={status} />
                </View>
                <View style={[styles.badge, { marginTop: 10 }]}>
                  {isVideo ? <Video color={colors.textSecondary} size={12} /> : <Search color={colors.textSecondary} size={12} />}
                  <Text variant="muted" style={{ fontSize: 10 }}>{isVideo ? t("Video + Article") : t("Article")}</Text>
                </View>
              </Pressable>
            );
          })}
        </View>

        {/* Glossary */}
        <View style={styles.between}>
          <Text variant="title">{t("Glossary")}</Text>
          <Pressable onPress={() => setFlashOpen(true)} style={styles.flashBtn} accessibilityRole="button">
            <Layers color={colors.bull} size={14} />
            <Text style={{ color: colors.bull, fontWeight: "700", fontSize: 12 }}>{t("Flashcards")}</Text>
          </Pressable>
        </View>
        <View style={styles.search}>
          <Search color={colors.textMuted} size={16} />
          <TextInput value={search} onChangeText={setSearch} placeholder={t("Search terms")} placeholderTextColor={colors.textMuted} style={{ flex: 1, color: colors.textPrimary }} accessibilityLabel={t("Search terms")} />
        </View>
        <View style={{ gap: 8 }}>
          {terms.map((term) => {
            const open = openTerm === term.en;
            return (
              <Pressable key={term.en} onPress={() => setOpenTerm(open ? null : term.en)} style={styles.term} accessibilityRole="button" accessibilityState={{ expanded: open }}>
                <View style={styles.between}>
                  <Text style={{ fontWeight: "600", flexShrink: 1 }} numberOfLines={1}>{term.en}</Text>
                  <Text style={{ fontFamily: fonts.urdu, color: colors.textSecondary, marginLeft: 8 }} numberOfLines={1}>{term.ur}</Text>
                </View>
                {open && <Text variant="secondary" style={{ marginTop: 6, fontSize: 13 }}>{term.def}</Text>}
              </Pressable>
            );
          })}
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>
      </KeyboardAvoidingView>

      <Pressable style={styles.fab} onPress={() => setTutorOpen(true)} accessibilityRole="button" accessibilityLabel={t("Ask AI Tutor")}>
        <Bot color={colors.bullForeground} size={24} />
      </Pressable>

      <FlashcardsModal visible={flashOpen} onClose={() => setFlashOpen(false)} />
      <TutorModal visible={tutorOpen} onClose={() => setTutorOpen(false)} />
      </SafeAreaView>
    </GlassScreen>
  );
}

function StatChip({ icon, label, color }: { icon: React.ReactNode; label: string; color: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, borderColor: color + "40", backgroundColor: color + "14" }}>
      {icon}
      <Text style={{ color, fontSize: 12, fontWeight: "600" }} numberOfLines={1}>{label}</Text>
    </View>
  );
}

function CompletionRing({ status }: { status: string }) {
  const { colors } = useTheme();
  if (status === "complete") {
    return (
      <View style={[ring, { backgroundColor: colors.bull, borderColor: colors.bull }]}>
        <Check color={colors.bullForeground} size={13} />
      </View>
    );
  }
  const border = status === "in-progress" ? colors.warning : colors.border;
  return <View style={[ring, { borderColor: border }]} />;
}
const ring = { width: 24, height: 24, borderRadius: 12, borderWidth: 2, alignItems: "center", justifyContent: "center" } as const;

/* ------------------------------ Flashcards ------------------------------- */
function FlashcardsModal({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { colors } = useTheme();
  const { t } = useLang();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [deck, setDeck] = useState(FLASHCARDS.map((_, i) => i));
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const total = FLASHCARDS.length;
  const done = pos >= deck.length;
  const card = !done ? FLASHCARDS[deck[pos]] : null;

  const next = () => { setFlipped(false); setPos((p) => p + 1); };
  const reviewAgain = () => { setFlipped(false); setDeck((d) => [...d, d[pos]]); setPos((p) => p + 1); };
  const restart = () => { setDeck(FLASHCARDS.map((_, i) => i)); setPos(0); setFlipped(false); };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <GlassScreen>
        <SafeAreaView style={[styles.safe, { padding: 16 }]}>
          <View style={styles.between}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Layers color={colors.textPrimary} size={18} />
            <Text variant="title">{t("Flashcards")}</Text>
          </View>
          <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
            <X color={colors.textSecondary} size={22} />
          </Pressable>
        </View>

        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 24 }}>
          {card ? (
            <>
              <Pressable style={styles.flashCard} onPress={() => setFlipped((f) => !f)} accessibilityLabel="Flip card">
                {!flipped ? (
                  <View style={{ alignItems: "center", gap: 12 }}>
                    <Text style={{ fontSize: 24, fontWeight: "700" }}>{card.front}</Text>
                    <Text style={{ fontFamily: fonts.urdu, fontSize: 28, color: colors.bull }}>{card.ur}</Text>
                    <Text variant="muted">{t("Tap to flip")}</Text>
                  </View>
                ) : (
                  <Text variant="secondary" style={{ textAlign: "center", fontSize: 15, lineHeight: 22 }}>{card.def}</Text>
                )}
              </Pressable>
              <View style={{ flexDirection: "row", gap: 12 }}>
                <Button title={t("Got it")} onPress={next} icon={<Check color={colors.bullForeground} size={16} />} />
                <Button title={t("Review Again")} variant="outline" onPress={reviewAgain} icon={<RotateCcw color={colors.textPrimary} size={16} />} />
              </View>
              <Text variant="mono" style={{ fontSize: 12 }}>{Math.min(pos + 1, total)} / {total} {t("terms")}</Text>
            </>
          ) : (
            <View style={{ alignItems: "center", gap: 8 }}>
              <PartyPopper color={colors.bull} size={40} />
              <Text variant="title">{t("Deck Complete!")}</Text>
              <Text variant="secondary">{t("You reviewed all")} {total} {t("terms")}.</Text>
              <View style={{ flexDirection: "row", gap: 12, marginTop: 12 }}>
                <Button title={t("Restart Deck")} onPress={restart} />
                <Button title={t("Exit")} variant="outline" onPress={onClose} />
              </View>
            </View>
          )}
          </View>
        </SafeAreaView>
      </GlassScreen>
    </Modal>
  );
}

/* --------------------------- AI content search --------------------------- */
const SOURCE_BADGE: Record<ApiLearnSearchResult["source_type"], { label: string; color: (c: ThemeColors) => string }> = {
  lesson_section: { label: "Lesson", color: (c) => c.bull },
  lesson_overview: { label: "Lesson", color: (c) => c.bull },
  glossary_term: { label: "Glossary", color: (c) => c.ai },
  quiz_explanation: { label: "Quiz", color: (c) => c.warning },
  learning_path: { label: "Path", color: (c) => c.textSecondary },
};

/**
 * LearnHub RAG search over lessons, glossary, quiz explanations and paths.
 * Debounced, network-backed; only renders when the backend feature flag is on
 * (the hook returns an empty list otherwise). Selecting a result opens the
 * matching lesson.
 */
function LearnSearchBox() {
  const { colors } = useTheme();
  const { lang, t, isUrdu } = useLang();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const [query, setQuery] = useState("");
  const { results, loading, isEmpty, hasQuery } = useLearnSearch(query, lang);

  function choose(r: ApiLearnSearchResult) {
    if (r.lesson_id) router.push(`/(tabs)/learn/lesson/${r.lesson_id}`);
    setQuery("");
  }

  return (
    <View style={{ gap: 8 }}>
      <View style={styles.search}>
        <Search color={colors.textMuted} size={16} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder={t("Search LearnHub…")}
          placeholderTextColor={colors.textMuted}
          style={{ flex: 1, color: colors.textPrimary }}
          accessibilityLabel={t("Search LearnHub…")}
        />
      </View>

      {loading && (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 4 }}>
          <ActivityIndicator color={colors.bull} size="small" />
          <Text variant="muted" style={{ fontSize: 12 }}>{t("Searching…")}</Text>
        </View>
      )}
      {hasQuery && !loading && isEmpty && (
        <Text variant="muted" style={{ fontSize: 12, paddingHorizontal: 4 }}>{t("No results found")}</Text>
      )}
      {results.map((r, i) => {
        const badge = SOURCE_BADGE[r.source_type];
        const badgeColor = badge.color(colors);
        const urduSnippet = isUrdu && r.snippet_ur != null;
        const snippet = urduSnippet ? r.snippet_ur : r.snippet_en;
        return (
          <Pressable
            key={`${r.source_type}-${r.lesson_id}-${r.section_id ?? ""}-${i}`}
            onPress={() => choose(r)}
            style={styles.searchResult}
            accessibilityRole="button"
            accessibilityLabel={`${t(badge.label)}: ${t(r.title)}`}
          >
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <View style={{ backgroundColor: badgeColor + "1a", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 }}>
                <Text style={{ color: badgeColor, fontSize: 10, fontWeight: "600" }}>{t(badge.label)}</Text>
              </View>
              <Text style={{ fontWeight: "600", fontSize: 13, flexShrink: 1 }} numberOfLines={1}>{t(r.title)}</Text>
            </View>
            {snippet ? (
              <Text
                variant="muted"
                style={[{ fontSize: 11, marginTop: 4 }, urduSnippet && { fontFamily: fonts.urdu, textAlign: "right" }]}
                numberOfLines={2}
              >
                {snippet}
              </Text>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

/* ------------------------------- AI Tutor -------------------------------- */
const HUB_PRESETS = ["What is the KSE-100 index?", "How do I start investing in PSX?", "Explain candlestick charts simply"];

function TutorModal({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { colors, mode } = useTheme();
  const { t, isUrdu } = useLang();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const { messages, loading, quotaExceeded, signedOut, send, abort } = useTutorChat({
    lessonTitle: "PSX investing basics",
    greeting: t("Hi! I'm your NafaIQ tutor. Ask me anything about PSX investing, terms, or strategies."),
    hydrate: true,
  });
  const [input, setInput] = useState("");
  const scrollRef = useRef<ScrollView>(null);

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

  const showPresets = messages.length === 1 && !signedOut;
  const disabled = loading || quotaExceeded;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={close}>
      <KeyboardAvoidingView style={styles.sheetWrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <Pressable style={StyleSheet.absoluteFill} onPress={close} accessibilityRole="button" accessibilityLabel={t("Close")} />
        <View style={styles.sheet}>
          <BlurView tint={mode === "light" ? "light" : "dark"} intensity={40} experimentalBlurMethod="dimezisBlurView" style={StyleSheet.absoluteFill} />
          <View style={[styles.between, styles.sheetHeader]}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Bot color={colors.bull} size={18} />
              <Text style={{ fontWeight: "700" }}>{t("Ask AI Tutor")}</Text>
            </View>
            <Pressable onPress={close} hitSlop={8} accessibilityRole="button" accessibilityLabel={t("Close")}>
              <X color={colors.textSecondary} size={22} />
            </Pressable>
          </View>

          <ScrollView ref={scrollRef} style={{ flex: 1 }} contentContainerStyle={{ padding: 12, gap: 10 }} onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}>
            {messages.map((m, i) => (
              <View key={i} style={[styles.bubble, m.role === "user" ? styles.bubbleUser : styles.bubbleAI]}>
                <TutorBubble content={m.content} role={m.role} color={m.role === "user" ? colors.bullForeground : colors.textPrimary} />
              </View>
            ))}
            {showPresets && (
              <View style={{ gap: 6, paddingTop: 4 }}>
                {HUB_PRESETS.map((p) => (
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
                <Text style={[{ color: colors.warning, fontSize: 12 }, isUrdu && { fontFamily: fonts.urdu }]}>
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
                <Text style={{ color: colors.bullForeground, fontWeight: "700", fontSize: 13 }}>{t("Sign in to chat with your tutor")}</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.inputBar}>
              <TextInput value={input} onChangeText={setInput} placeholder={t("Ask about investing…")} placeholderTextColor={colors.textMuted} style={[styles.chatInput, disabled && { opacity: 0.5 }]} editable={!disabled} onSubmitEditing={() => submit(input)} accessibilityLabel={t("Message the tutor")} />
              <Pressable onPress={() => submit(input)} disabled={disabled} style={[styles.sendBtn, disabled && { opacity: 0.5 }]} accessibilityRole="button" accessibilityLabel={t("Send")}>
                <Send color={colors.bullForeground} size={16} />
              </Pressable>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1 },
    content: { padding: 16, gap: 16 },
    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 6 },
    pathCard: { width: 220, borderWidth: 1, borderLeftWidth: 3, borderColor: c.border, borderRadius: 12, backgroundColor: c.glassFillStrong, padding: 16 },
    pathIcon: { width: 40, height: 40, borderRadius: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, alignItems: "center", justifyContent: "center" },
    pathBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, borderRadius: 8, paddingVertical: 9, marginTop: 12 },
    grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
    lessonCard: { width: "47%", flexGrow: 1, borderWidth: 1, borderColor: c.border, borderRadius: radii.card, backgroundColor: c.glassFillStrong, padding: 14 },
    lessonIcon: { width: 40, height: 40, borderRadius: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, alignItems: "center", justifyContent: "center" },
    badge: { flexDirection: "row", alignItems: "center", gap: 4, alignSelf: "flex-start", backgroundColor: c.glassFill, borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
    flashBtn: { flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderColor: c.bull + "66", backgroundColor: c.bull + "1a", borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6 },
    search: { flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFillStrong, borderRadius: radii.btn, paddingHorizontal: 12, minHeight: 44 },
    searchResult: { borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFillStrong, borderRadius: 8, padding: 12, minHeight: 44 },
    term: { borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFillStrong, borderRadius: 8, padding: 12 },
    fab: { position: "absolute", right: 16, bottom: 24, width: 56, height: 56, borderRadius: 28, backgroundColor: c.bull, alignItems: "center", justifyContent: "center", elevation: 6 },
    flashCard: { width: "100%", minHeight: 240, borderWidth: 1, borderColor: c.border, borderRadius: 16, backgroundColor: c.glassFillStrong, padding: 28, alignItems: "center", justifyContent: "center" },
    sheetWrap: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.6)" },
    sheet: { height: "80%", backgroundColor: c.glassFillStrong, borderTopLeftRadius: 16, borderTopRightRadius: 16, borderTopWidth: 1, borderColor: c.border, overflow: "hidden" },
    sheetHeader: { paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: c.border },
    bubble: { maxWidth: "88%", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8 },
    bubbleUser: { alignSelf: "flex-end", backgroundColor: c.bull, borderBottomRightRadius: 2 },
    bubbleAI: { alignSelf: "flex-start", backgroundColor: c.glassFill, borderBottomLeftRadius: 2 },
    preset: { borderWidth: 1, borderColor: c.border, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8, minHeight: 44, justifyContent: "center" },
    quota: { borderWidth: 1, borderColor: c.warning + "66", backgroundColor: c.warning + "1a", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
    signedOut: { padding: 12, borderTopWidth: 1, borderTopColor: c.border, alignItems: "center" },
    signInBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: c.bull, borderRadius: 8, paddingHorizontal: 16, minHeight: 44 },
    inputBar: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: c.border },
    chatInput: { flex: 1, minHeight: 44, borderWidth: 1, borderColor: c.border, borderRadius: 8, paddingHorizontal: 12, color: c.textPrimary, backgroundColor: c.glassFill },
    sendBtn: { width: 44, height: 44, borderRadius: 8, backgroundColor: c.bull, alignItems: "center", justifyContent: "center" },
  });
