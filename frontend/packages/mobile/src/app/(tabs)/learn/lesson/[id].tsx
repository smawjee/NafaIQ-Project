// Lesson detail (`/learn/lesson/[id]`). Mirrors web /learn/lesson/$id: reading
// mode (progress bar, blocks, video), quiz (timer + feedback), results (score
// ring + XP), per-lesson AI tutor, prev/next nav. Theme + i18n.
import { useLocalSearchParams, useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle } from "react-native-svg";

import { TutorMessage as AiText } from "@/components/ai/AiText";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { TutorSheet } from "@/components/TutorSheet";
import { Button, Text } from "@/components/ui";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { fonts, radii, type ThemeColors } from "@/constants/theme";
import { useLessonSummary, useQuizExplanation } from "@/hooks/ai/use-learn-ai";
import { useLearnRagStatus, useRelatedLessons } from "@/hooks/ai/use-learn-search";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { useLearn } from "@/hooks/use-learn";
import { useTheme } from "@/hooks/use-theme";
import { lessonOrder, xpForScore } from "@nafaiq/shared";
import { LESSON_CONTENT, type ContentBlock, type LessonContent } from "@nafaiq/shared";
import { ArrowLeft, Bookmark, Bot, Check, ChevronRight, iconFor, Info, Lightbulb, Play, RotateCcw, Sparkles, TriangleAlert, X } from "@/lib/icons";

const FALLBACK = Object.keys(LESSON_CONTENT)[0];

export default function LessonScreen() {
  const { id: rawId } = useLocalSearchParams<{ id: string }>();
  const id = LESSON_CONTENT[rawId ?? ""] ? (rawId as string) : FALLBACK;
  const lesson = LESSON_CONTENT[id];
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const { statusOf, completeLesson, toggleBookmark, bookmarks } = useLearn();

  const [mode, setMode] = useState<"reading" | "quiz" | "results">("reading");
  const [tutorOpen, setTutorOpen] = useState(false);
  const [scrollPct, setScrollPct] = useState(0);
  const [score, setScore] = useState(0);

  const order = useMemo(() => lessonOrder(), []);
  const idx = order.indexOf(id);
  const nextId = idx >= 0 && idx < order.length - 1 ? order[idx + 1] : null;
  const prevId = idx > 0 ? order[idx - 1] : null;
  const bookmarked = bookmarks.includes(id);

  function finishQuiz(correct: number) {
    setScore(correct);
    if (correct >= 2) completeLesson(id, xpForScore(correct, lesson.quiz.length));
    setMode("results");
  }

  return (
    <GlassScreen>
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <View style={styles.topbar}>
        <Pressable onPress={() => router.back()} hitSlop={8} accessibilityRole="button" accessibilityLabel="Back">
          <ArrowLeft color={colors.textPrimary} size={22} />
        </Pressable>
        <Text style={{ flex: 1, fontWeight: "600" }} numberOfLines={1}>{lesson.title}</Text>
        <Pressable onPress={() => toggleBookmark(id)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Bookmark">
          <Bookmark color={bookmarked ? colors.gold : colors.textMuted} fill={bookmarked ? colors.gold : "none"} size={20} />
        </Pressable>
        <Pressable onPress={() => setTutorOpen(true)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Ask AI">
          <Bot color={colors.bull} size={20} />
        </Pressable>
      </View>
      {mode === "reading" && <ProgressBar value={scrollPct} color={lesson.accent} height={3} track={colors.background} />}

      {mode === "reading" && (
        <Reading
          lesson={lesson}
          lessonId={id}
          statusComplete={statusOf(id) === "complete"}
          onScrollPct={setScrollPct}
          onStartQuiz={() => setMode("quiz")}
          onWatched={() => completeLesson(id, 30)}
          onPrev={prevId ? () => router.replace(`/(tabs)/learn/lesson/${prevId}`) : undefined}
          onNext={nextId ? () => router.replace(`/(tabs)/learn/lesson/${nextId}`) : undefined}
        />
      )}
      {mode === "quiz" && <Quiz lesson={lesson} lessonId={id} onFinish={finishQuiz} />}
      {mode === "results" && (
        <Results
          lesson={lesson}
          score={score}
          onRetake={() => setMode("quiz")}
          onContinue={() => (nextId ? router.replace(`/(tabs)/learn/lesson/${nextId}`) : router.replace("/(tabs)/learn"))}
          onBack={() => router.replace("/(tabs)/learn")}
        />
      )}

      <TutorSheet visible={tutorOpen} onClose={() => setTutorOpen(false)} lessonTitle={lesson.title} presets={lesson.presets} greeting={`Ask me anything about "${lesson.title}".`} />
      </SafeAreaView>
    </GlassScreen>
  );
}

/* ------------------------------- Reading --------------------------------- */
function Reading({
  lesson,
  lessonId,
  statusComplete,
  onScrollPct,
  onStartQuiz,
  onWatched,
  onPrev,
  onNext,
}: {
  lesson: LessonContent;
  lessonId: string;
  statusComplete: boolean;
  onScrollPct: (p: number) => void;
  onStartQuiz: () => void;
  onWatched: () => void;
  onPrev?: () => void;
  onNext?: () => void;
}) {
  const { colors } = useTheme();
  const { t } = useLang();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const Icon = iconFor(lesson.emoji);
  return (
    <ScrollView
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      scrollEventThrottle={16}
      onScroll={(e) => {
        const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
        const max = contentSize.height - layoutMeasurement.height;
        onScrollPct(max > 0 ? Math.min(1, contentOffset.y / max) : 0);
      }}
    >
      <View style={[styles.hero, { borderColor: lesson.accent + "55", backgroundColor: lesson.accent + "12" }]}>
        <View style={[styles.heroIcon, { backgroundColor: lesson.accent + "22" }]}>
          <Icon color={lesson.accent} size={22} />
        </View>
        <Text variant="muted" style={{ marginTop: 8 }}>{t(lesson.category)}</Text>
        <Text variant="display" style={{ fontSize: 22 }}>{lesson.title}</Text>
        <Text variant="secondary">{lesson.subtitle}</Text>
        <Text variant="muted" style={{ marginTop: 4 }}>{lesson.duration} · {t(lesson.level)}</Text>
      </View>

      {lesson.type === "video" && lesson.videoUrl && (
        <GlassCard style={{ gap: 12, alignItems: "center", padding: 16 }}>
          <View style={[styles.heroIcon, { backgroundColor: lesson.accent + "22" }]}>
            <Play color={lesson.accent} size={22} />
          </View>
          <Text variant="secondary">{t("Watch the video lesson")}</Text>
          <View style={{ flexDirection: "row", gap: 10 }}>
            <Button title={t("Play")} onPress={() => WebBrowser.openBrowserAsync(lesson.videoUrl!)} />
            <Button title={t("Mark as Watched")} variant="outline" onPress={onWatched} />
          </View>
        </GlassCard>
      )}

      {lesson.sections.map((s) => (
        <View key={s.id} style={{ gap: 10 }}>
          <Text variant="title">{s.heading}</Text>
          {s.blocks.map((b, i) => (
            <Block key={i} block={b} />
          ))}
        </View>
      ))}

      <LessonSummaryCard lessonId={lessonId} />
      <RelatedLessons lessonId={lessonId} />

      <Button title={statusComplete ? t("Retake the Quiz") : t("Take the Quiz")} onPress={onStartQuiz} icon={<ChevronRight color={colors.primaryForeground} size={16} />} />

      <View style={styles.navRow}>
        <View style={{ flex: 1 }}>{onPrev ? <Button title={`‹ ${t("Previous")}`} variant="outline" onPress={onPrev} /> : null}</View>
        <View style={{ flex: 1 }}>{onNext ? <Button title={`${t("Next")} ›`} variant="outline" onPress={onNext} /> : null}</View>
      </View>
      <View style={{ height: 20 }} />
    </ScrollView>
  );
}

function Block({ block }: { block: ContentBlock }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  if (block.type === "p") {
    return <Text variant="secondary" style={{ fontSize: 15, lineHeight: 22 }}>{block.text}</Text>;
  }
  if (block.type === "callout") {
    const map = {
      tip: { c: colors.bull, Icon: Lightbulb },
      note: { c: colors.info, Icon: Info },
      example: { c: colors.gold, Icon: Info },
      warning: { c: colors.bear, Icon: TriangleAlert },
    } as const;
    const { c, Icon } = map[block.kind];
    return (
      <View style={[styles.callout, { borderLeftColor: c, backgroundColor: c + "12" }]}>
        <Icon color={c} size={15} />
        <Text variant="secondary" style={{ flex: 1, fontSize: 14 }}>{block.text}</Text>
      </View>
    );
  }
  if (block.type === "formula") {
    return (
      <View style={styles.formula}>
        {block.lines.map((l, i) => (
          <Text key={i} style={{ fontFamily: fonts.mono, color: colors.textPrimary, fontSize: 13 }}>{l}</Text>
        ))}
      </View>
    );
  }
  return (
    <View style={styles.table}>
      <View style={[styles.tr, { backgroundColor: colors.glassFill }]}>
        {block.head.map((h, i) => (
          <Text key={i} style={[styles.td, { fontWeight: "700", fontSize: 12 }]}>{h}</Text>
        ))}
      </View>
      {block.rows.map((row, ri) => (
        <View key={ri} style={[styles.tr, ri > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
          {row.map((cell, ci) => (
            <Text key={ci} variant="secondary" style={[styles.td, { fontSize: 12 }]}>{cell}</Text>
          ))}
        </View>
      ))}
    </View>
  );
}

/* --------------------------------- Quiz ---------------------------------- */
function Quiz({ lesson, lessonId, onFinish }: { lesson: LessonContent; lessonId: string; onFinish: (correct: number) => void }) {
  const { colors } = useTheme();
  const { t, lang } = useLang();
  const { user } = useAuth();
  const { enabled: ragEnabled } = useLearnRagStatus();
  const explain = useQuizExplanation();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const questions = useMemo(
    () =>
      lesson.quiz.map((q) => {
        const opts = q.options.map((text, i) => ({ text, correct: i === q.correct }));
        for (let i = opts.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [opts[i], opts[j]] = [opts[j], opts[i]];
        }
        return { ...q, opts };
      }),
    [lesson],
  );

  const [qi, setQi] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [timeLeft, setTimeLeft] = useState(30);
  const q = questions[qi];

  // Each question gets its own AI explanation — drop the previous one when the
  // question changes so a stale answer never shows on the next card.
  const { reset: resetExplanation } = explain;
  useEffect(() => {
    setTimeLeft(30);
    setPicked(null);
    resetExplanation();
    if (!q) return;
    const timer = setInterval(() => setTimeLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [qi, q, resetExplanation]);

  useEffect(() => {
    if (timeLeft === 0 && picked === null) setPicked(-1);
  }, [timeLeft, picked]);

  function choose(i: number) {
    if (picked !== null) return;
    setPicked(i);
    if (q.opts[i].correct) setCorrectCount((c) => c + 1);
  }
  function next() {
    if (qi < questions.length - 1) setQi((n) => n + 1);
    else onFinish(correctCount);
  }

  const revealed = picked !== null;
  const timerColor = timeLeft > 15 ? colors.bull : timeLeft > 7 ? colors.warning : colors.bear;

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.between}>
        <Text variant="muted">{t("Question")} {qi + 1} / {questions.length}</Text>
        <Text style={{ color: timerColor, fontFamily: fonts.mono, fontWeight: "700" }}>{timeLeft}s</Text>
      </View>
      <View style={{ flexDirection: "row", gap: 6 }}>
        {questions.map((_, i) => (
          <View key={i} style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: i < qi ? colors.bull : i === qi ? colors.warning : colors.surfaceAlt }} />
        ))}
      </View>

      <Text variant="title" style={{ marginTop: 4 }}>{q.q}</Text>
      <View style={{ gap: 10 }}>
        {q.opts.map((o, i) => {
          const isPicked = picked === i;
          const showCorrect = revealed && o.correct;
          const showWrong = revealed && isPicked && !o.correct;
          const border = showCorrect ? colors.bull : showWrong ? colors.bear : isPicked ? colors.primary : colors.border;
          const bg = showCorrect ? colors.bull + "1a" : showWrong ? colors.bear + "1a" : "transparent";
          return (
            <Pressable key={i} onPress={() => choose(i)} disabled={revealed} accessibilityRole="button" style={[styles.option, { borderColor: border, backgroundColor: bg }]}>
              <Text style={{ flex: 1 }}>{o.text}</Text>
              {showCorrect && <Check color={colors.bull} size={18} />}
              {showWrong && <X color={colors.bear} size={18} />}
            </Pressable>
          );
        })}
      </View>

      {revealed && (
        <GlassCard style={{ gap: 6, padding: 16, borderColor: colors.ai + "44" }}>
          <Text style={{ color: colors.ai, fontWeight: "700" }}>{t("Explanation")}</Text>
          <Text variant="secondary">{q.explanation}</Text>

          {/* Opt-in deep AI explanation. The static line above always stands;
              this only fires on an explicit tap so it never silently spends the
              learner's daily AI budget. Gated on the flag + a signed-in user. */}
          {ragEnabled && user && !explain.data && (
            <Pressable
              onPress={() =>
                explain.mutate({
                  lessonId,
                  question: q.q,
                  selectedOption: picked !== null && picked >= 0 ? q.opts[picked].text : "",
                  correctOption: q.opts.find((o) => o.correct)?.text ?? "",
                  lang,
                })
              }
              disabled={explain.isPending}
              style={styles.explainBtn}
              accessibilityRole="button"
              accessibilityLabel={t("Explain in depth")}
            >
              {explain.isPending ? (
                <>
                  <ActivityIndicator color={colors.ai} size="small" />
                  <Text style={{ color: colors.textMuted, fontSize: 12 }}>{t("Analyzing…")}</Text>
                </>
              ) : (
                <>
                  <Sparkles color={colors.ai} size={14} />
                  <Text style={{ color: colors.textSecondary, fontSize: 12, fontWeight: "600" }}>{t("Explain in depth")}</Text>
                </>
              )}
            </Pressable>
          )}

          {/* The endpoint answered but had nothing to ground on. Say so in one
              muted line — the static explanation above still stands. */}
          {explain.data && !explain.data.explanation && (
            <Text variant="muted" style={{ fontSize: 12 }}>{t("No AI explanation available right now.")}</Text>
          )}

          {explain.data?.explanation && (
            <View style={{ gap: 6, marginTop: 4, borderTopWidth: 1, borderTopColor: colors.ai + "26", paddingTop: 10 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                <Sparkles color={colors.ai} size={13} />
                <Text style={{ color: colors.ai, fontWeight: "700", fontSize: 12 }}>{t("AI explanation")}</Text>
              </View>
              <AiText content={explain.data.explanation} role="assistant" color={colors.textSecondary} />
              {explain.data.sources.length > 0 && (
                <Text variant="muted" style={{ fontSize: 11 }}>{t("Based on")} {explain.data.sources.join(" · ")}</Text>
              )}
            </View>
          )}
        </GlassCard>
      )}

      {revealed && <Button title={qi < questions.length - 1 ? t("Next Question") : t("See Results")} onPress={next} />}
      <View style={{ height: 20 }} />
    </ScrollView>
  );
}

/* -------------------------------- Results -------------------------------- */
function Results({
  lesson,
  score,
  onRetake,
  onContinue,
  onBack,
}: {
  lesson: LessonContent;
  score: number;
  onRetake: () => void;
  onContinue: () => void;
  onBack: () => void;
}) {
  const { colors } = useTheme();
  const { t } = useLang();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const total = lesson.quiz.length;
  const xp = xpForScore(score, total);
  const msg = score >= total ? t("Perfect! You've mastered this.") : score >= 2 ? t("Great work — lesson complete!") : t("Good try — review and retake to complete.");

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={{ alignItems: "center", gap: 12, paddingVertical: 12 }}>
        <ScoreRing correct={score} total={total} />
        <Text variant="title">{msg}</Text>
        <Text style={{ color: colors.gold, fontFamily: fonts.mono, fontWeight: "700" }}>+{xp} XP</Text>
      </View>

      <Text variant="title">{t("Review")}</Text>
      {lesson.quiz.map((q, i) => (
        <GlassCard key={i} style={{ gap: 6, padding: 14 }}>
          <Text style={{ fontWeight: "600" }}>{q.q}</Text>
          <Text style={{ color: colors.bull, fontSize: 13 }}>✓ {q.options[q.correct]}</Text>
          <Text variant="muted" style={{ fontSize: 12 }}>{q.explanation}</Text>
        </GlassCard>
      ))}

      <View style={{ gap: 10, marginTop: 4 }}>
        <Button title={t("Continue")} onPress={onContinue} />
        <View style={{ flexDirection: "row", gap: 10 }}>
          <View style={{ flex: 1 }}>
            <Button title={t("Retake")} variant="outline" onPress={onRetake} icon={<RotateCcw color={colors.textPrimary} size={16} />} />
          </View>
          <View style={{ flex: 1 }}>
            <Button title={t("Back to Learn")} variant="ghost" onPress={onBack} />
          </View>
        </View>
      </View>
      <View style={{ height: 20 }} />
    </ScrollView>
  );
}

function ScoreRing({ correct, total }: { correct: number; total: number }) {
  const { colors } = useTheme();
  const { t } = useLang();
  const size = 130, sw = 12, r = (size - sw) / 2, c = 2 * Math.PI * r;
  const pct = total > 0 ? correct / total : 0;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <Svg width={size} height={size}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.surfaceAlt} strokeWidth={sw} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={pct >= 0.5 ? colors.bull : colors.warning}
          strokeWidth={sw}
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <View style={{ position: "absolute", alignItems: "center" }}>
        <Text variant="display">{correct}/{total}</Text>
        <Text variant="muted">{t("correct")}</Text>
      </View>
    </View>
  );
}

/* --------------------------- AI lesson summary --------------------------- */
/**
 * "Key ideas from this lesson" — an on-demand, AI-generated recap grounded in
 * the lesson's own content. Opt-in: renders as a modest button and only calls
 * the model on tap. Renders nothing when the flag is off, the user is signed
 * out, or the result is empty — a reading page shows no error box for an
 * optional affordance.
 */
function LessonSummaryCard({ lessonId }: { lessonId: string }) {
  const { colors } = useTheme();
  const { t } = useLang();
  const { user } = useAuth();
  const { enabled } = useLearnRagStatus();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { mutate, data, isPending } = useLessonSummary(lessonId);

  // `user` as well as the flag: /api/learn/ai/* needs a Supabase JWT, so for a
  // signed-out reader this button could only ever 401 and vanish on tap.
  if (!enabled || !user) return null;

  if (isPending) {
    return (
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <ActivityIndicator color={colors.ai} size="small" />
        <Text variant="muted" style={{ fontSize: 12 }}>{t("Analyzing…")}</Text>
      </View>
    );
  }

  if (!data) {
    return (
      <Pressable onPress={() => mutate()} style={styles.explainBtn} accessibilityRole="button" accessibilityLabel={t("Key ideas from this lesson")}>
        <Sparkles color={colors.ai} size={14} />
        <Text style={{ color: colors.textSecondary, fontSize: 12, fontWeight: "600" }}>{t("Key ideas from this lesson")}</Text>
      </Pressable>
    );
  }

  // The one failure worth a word — the learner just tapped, so silence would
  // read as a broken button. Every other failure stays silent below.
  if (data.limited) {
    return <Text variant="muted" style={{ fontSize: 12 }}>{t("Daily AI limit reached — try again tomorrow.")}</Text>;
  }

  if (data.key_ideas.length === 0) return null;

  return (
    <View style={styles.summaryCard}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <Sparkles color={colors.ai} size={14} />
        <Text style={{ fontWeight: "700", fontSize: 13 }}>{t("Key ideas from this lesson")}</Text>
        <View style={{ backgroundColor: colors.ai + "26", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 }}>
          <Text style={{ color: colors.ai, fontSize: 9, fontWeight: "700" }}>{t("AI generated")}</Text>
        </View>
      </View>

      <View style={{ gap: 6, marginTop: 8 }}>
        {data.key_ideas.map((idea) => (
          <View key={idea} style={{ flexDirection: "row", gap: 6 }}>
            <Text style={{ color: colors.ai }}>{"•"}</Text>
            <View style={{ flex: 1 }}>
              <AiText content={idea} role="assistant" color={colors.textSecondary} />
            </View>
          </View>
        ))}
      </View>

      {data.terms.length > 0 && (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
          {data.terms.map((term) => (
            <View key={term} style={styles.termChip}>
              <Text style={{ color: colors.textSecondary, fontSize: 11 }}>{term}</Text>
            </View>
          ))}
        </View>
      )}

      {data.pitfall && (
        <View style={styles.pitfall}>
          <Text style={{ color: colors.warning, fontSize: 10, fontWeight: "700", textTransform: "uppercase" }}>{t("Common mistake")}</Text>
          <Text variant="secondary" style={{ fontSize: 12, marginTop: 2 }}>{data.pitfall}</Text>
        </View>
      )}

      {data.sources.length > 0 && (
        <Text variant="muted" style={{ fontSize: 11, marginTop: 10 }}>{t("Based on")}: {data.sources.join(" · ")}</Text>
      )}

      <Text variant="muted" style={{ fontSize: 10, marginTop: 6 }}>{t("Summarised by AI from this lesson. Not financial advice.")}</Text>
    </View>
  );
}

/* ---------------------------- Related lessons ---------------------------- */
/**
 * "Related topics" — lessons ranked by content similarity to this one. Renders
 * nothing when the flag is off, the API errors, or a related id has no body.
 */
function RelatedLessons({ lessonId }: { lessonId: string }) {
  const { colors } = useTheme();
  const { t } = useLang();
  const router = useRouter();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const related = useRelatedLessons(lessonId, 4);

  const items = related
    .map((r) => ({ lesson_id: r.lesson_id, lesson: LESSON_CONTENT[r.lesson_id] }))
    .filter((r) => Boolean(r.lesson));

  if (items.length === 0) return null;

  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <Sparkles color={colors.ai} size={14} />
        <Text style={{ fontWeight: "700", fontSize: 13 }}>{t("Related topics")}</Text>
      </View>
      <View style={{ gap: 8 }}>
        {items.map(({ lesson_id, lesson }) => (
          <Pressable
            key={lesson_id}
            onPress={() => router.replace(`/(tabs)/learn/lesson/${lesson_id}`)}
            style={styles.relatedCard}
            accessibilityRole="button"
            accessibilityLabel={t(lesson.title)}
          >
            <Text style={{ fontWeight: "600", fontSize: 13 }} numberOfLines={1}>{t(lesson.title)}</Text>
            {lesson.sections[0] && (
              <Text variant="muted" style={{ fontSize: 11, marginTop: 2 }} numberOfLines={1}>{t(lesson.sections[0].heading)}</Text>
            )}
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1 },
    topbar: { flexDirection: "row", alignItems: "center", gap: 14, paddingHorizontal: 16, paddingVertical: 10 },
    content: { padding: 16, gap: 16 },
    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    hero: { borderWidth: 1, borderRadius: radii.card, padding: 16, gap: 2 },
    heroIcon: { width: 44, height: 44, borderRadius: 10, alignItems: "center", justifyContent: "center" },
    callout: { flexDirection: "row", gap: 8, borderLeftWidth: 3, borderRadius: 8, padding: 10 },
    formula: { backgroundColor: c.glassFill, borderRadius: 8, padding: 12, gap: 2 },
    table: { borderWidth: 1, borderColor: c.border, borderRadius: 8, overflow: "hidden" },
    tr: { flexDirection: "row" },
    td: { flex: 1, padding: 8, color: c.textPrimary },
    navRow: { flexDirection: "row", gap: 10 },
    option: { flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderRadius: radii.btn, padding: 14, minHeight: 48 },
    explainBtn: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start", borderWidth: 1, borderColor: c.border, borderRadius: radii.btn, paddingHorizontal: 12, paddingVertical: 8, marginTop: 4, minHeight: 44 },
    summaryCard: { borderWidth: 1, borderColor: c.ai + "33", backgroundColor: c.ai + "0d", borderRadius: radii.card, padding: 16 },
    termChip: { backgroundColor: c.glassFill, borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3 },
    pitfall: { borderLeftWidth: 2, borderLeftColor: c.warning, backgroundColor: c.glassFill, borderRadius: radii.btn, paddingHorizontal: 10, paddingVertical: 6, marginTop: 10 },
    relatedCard: { borderWidth: 1, borderColor: c.border, borderRadius: radii.btn, padding: 12, minHeight: 44 },
  });
