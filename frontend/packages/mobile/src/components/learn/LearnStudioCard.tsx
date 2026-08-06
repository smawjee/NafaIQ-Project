import * as DocumentPicker from "expo-document-picker";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from "react-native";

import type { StudioLevel, StudioProject } from "@nafaiq/shared";

import { GlassCard } from "@/components/glass/GlassCard";
import { Button, Text } from "@/components/ui";
import { ChipRow, Segmented } from "@/components/ui/controls";
import { fonts, radii, type ThemeColors } from "@/constants/theme";
import {
  useCreateStudioPdfProject,
  useCreateStudioProject,
  useDeleteStudioProject,
  useStudioProjects,
  useStudioStatus,
} from "@/hooks/queries/use-learn-studio";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { BookOpen, FileText, FileUp, Sparkles, Trash2, Video } from "@/lib/icons";

const LEVEL_LABELS: Record<StudioLevel, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

const LEVEL_BY_LABEL = Object.fromEntries(
  Object.entries(LEVEL_LABELS).map(([key, value]) => [value, key]),
) as Record<string, StudioLevel>;

const STAGE_LABELS: Record<string, string> = {
  queued: "Preparing lesson",
  extracting_document: "Reading private PDF",
  retrieving_sources: "Finding trusted sources",
  generating_lesson: "Writing lesson and quiz",
  validating: "Checking citations",
  ready: "Ready to study",
  video_queued: "Video queued",
  writing_storyboard: "Writing storyboard",
  generating_audio: "Generating narration",
  rendering: "Rendering video",
  uploading: "Preparing secure playback",
  video_failed: "Video needs retry",
};

export function LearnStudioCard() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { user } = useAuth();
  const { lang, t } = useLang();
  const router = useRouter();
  const status = useStudioStatus(Boolean(user));
  const enabled = Boolean(status.data?.enabled);
  const projects = useStudioProjects(Boolean(user) && enabled);
  const createTopic = useCreateStudioProject();
  const createPdf = useCreateStudioPdfProject();
  const remove = useDeleteStudioProject();

  const [mode, setMode] = useState<"Topic" | "PDF">("Topic");
  const [topic, setTopic] = useState("");
  const [pdfFocus, setPdfFocus] = useState("");
  const [level, setLevel] = useState<StudioLevel>("beginner");
  const [file, setFile] = useState<DocumentPicker.DocumentPickerAsset | null>(null);
  const [fileError, setFileError] = useState("");

  const busy = createTopic.isPending || createPdf.isPending;
  const error = createTopic.error ?? createPdf.error;

  const openProject = (projectId: string) =>
    router.push(`/(tabs)/learn/generated/${projectId}` as never);

  const submitTopic = async () => {
    const value = topic.trim();
    if (value.length < 3 || busy || !enabled) return;
    try {
      const project = await createTopic.mutateAsync({
        topic: value,
        lang,
        level,
        targetMinutes: 4,
      });
      setTopic("");
      openProject(project.id);
    } catch {
      // The mutation error is rendered inside the card.
    }
  };

  const pickPdf = async () => {
    setFileError("");
    const result = await DocumentPicker.getDocumentAsync({
      type: "application/pdf",
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled) return;
    const selected = result.assets[0];
    const limit = status.data?.pdfMaxBytes ?? 15 * 1024 * 1024;
    if ((selected.size ?? 0) > limit) {
      setFile(null);
      setFileError(t("PDF exceeds the 15 MB limit."));
      return;
    }
    setFile(selected);
  };

  const submitPdf = async () => {
    if (!file || busy || !enabled) return;
    try {
      const project = await createPdf.mutateAsync({
        uri: file.uri,
        filename: file.name,
        mimeType: file.mimeType,
        size: file.size,
        topic: pdfFocus,
        lang,
        level,
        targetMinutes: 4,
      });
      setFile(null);
      setPdfFocus("");
      openProject(project.id);
    } catch {
      // The mutation error is rendered inside the card.
    }
  };

  const confirmDelete = (project: StudioProject) => {
    Alert.alert(
      t("Delete lesson"),
      t("Delete this lesson and its private uploaded files?"),
      [
        { text: t("Cancel"), style: "cancel" },
        {
          text: t("Delete"),
          style: "destructive",
          onPress: () => remove.mutate(project.id),
        },
      ],
    );
  };

  return (
    <GlassCard style={styles.card}>
      <View style={styles.headingRow}>
        <View style={styles.iconWrap}>
          <Sparkles color={colors.ai} size={20} />
        </View>
        <View style={{ flex: 1, gap: 3 }}>
          <Text variant="title">{t("Create your own PSX lesson")}</Text>
          <Text variant="secondary" style={styles.description}>
            {t("Generate source-grounded notes, flashcards, a quiz, and an optional narrated video.")}
          </Text>
        </View>
      </View>

      {status.isLoading ? (
        <ActivityIndicator color={colors.ai} />
      ) : !enabled ? (
        <View style={styles.disabledNotice} accessibilityRole="alert">
          <Text style={{ color: colors.warning, fontWeight: "700" }}>
            {t("LearnHub Studio is not enabled on this backend yet.")}
          </Text>
          <Text variant="muted">
            {t("Your official LearnHub lessons remain available below.")}
          </Text>
        </View>
      ) : (
        <>
          <Segmented options={["Topic", "PDF"]} value={mode} onChange={(value) => setMode(value as "Topic" | "PDF")} />

          <ChipRow
            options={Object.values(LEVEL_LABELS).map(t)}
            value={t(LEVEL_LABELS[level])}
            onChange={(label) => {
              const untranslated = Object.values(LEVEL_LABELS).find((value) => t(value) === label) ?? label;
              setLevel(LEVEL_BY_LABEL[untranslated] ?? "beginner");
            }}
          />

          {mode === "Topic" ? (
            <View style={{ gap: 10 }}>
              <View style={styles.inputRow}>
                <BookOpen color={colors.textMuted} size={17} />
                <TextInput
                  value={topic}
                  onChangeText={setTopic}
                  maxLength={160}
                  placeholder={t("e.g. How dividends work on PSX")}
                  placeholderTextColor={colors.textMuted}
                  style={styles.input}
                  accessibilityLabel={t("PSX lesson topic")}
                />
              </View>
              <Button
                title={createTopic.isPending ? t("Creating…") : t("Create lesson")}
                onPress={submitTopic}
                loading={createTopic.isPending}
                disabled={topic.trim().length < 3}
              />
            </View>
          ) : (
            <View style={{ gap: 10 }}>
              <Pressable
                onPress={pickPdf}
                style={styles.pdfPicker}
                accessibilityRole="button"
                accessibilityLabel={t("Select a private PDF")}
              >
                <FileUp color={colors.ai} size={21} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "700" }} numberOfLines={1}>
                    {file?.name ?? t("Select a private PDF")}
                  </Text>
                  <Text variant="muted">
                    {t("PDF only · Up to 15 MB and 100 pages · Kept private")}
                  </Text>
                </View>
              </Pressable>
              <View style={styles.inputRow}>
                <FileText color={colors.textMuted} size={17} />
                <TextInput
                  value={pdfFocus}
                  onChangeText={setPdfFocus}
                  maxLength={160}
                  placeholder={t("Optional focus, e.g. explain the dividend policy")}
                  placeholderTextColor={colors.textMuted}
                  style={styles.input}
                  accessibilityLabel={t("Lesson focus")}
                />
              </View>
              {fileError ? <Text style={{ color: colors.bear }}>{fileError}</Text> : null}
              <Button
                title={createPdf.isPending ? t("Uploading…") : t("Create from PDF")}
                onPress={submitPdf}
                loading={createPdf.isPending}
                disabled={!file}
              />
            </View>
          )}

          {error ? (
            <Text accessibilityRole="alert" style={{ color: colors.bear, fontSize: 12 }}>
              {error instanceof Error
                ? error.message
                : t("The lesson could not be started. Please try again.")}
            </Text>
          ) : null}

          <View style={styles.limitRow}>
            <Video color={colors.textMuted} size={13} />
            <Text variant="muted">
              {`${status.data?.packDailyLimit ?? 5} ${t("study packs")} · ${status.data?.videoDailyLimit ?? 1} ${t("video per day")} · ${t("Educational content only")}`}
            </Text>
          </View>

          {projects.data?.projects.length ? (
            <View style={styles.library}>
              <Text variant="title" style={{ fontSize: 15 }}>
                {t("Your generated lessons")}
              </Text>
              {projects.data.projects.map((project) => (
                <View key={project.id} style={styles.projectRow}>
                  <Pressable
                    onPress={() => openProject(project.id)}
                    style={{ flex: 1, gap: 3 }}
                    accessibilityRole="button"
                    accessibilityLabel={`${t("Open lesson")}: ${project.topic}`}
                  >
                    <Text style={{ fontWeight: "700" }} numberOfLines={1}>
                      {project.topic}
                    </Text>
                    {project.documentName ? (
                      <Text style={{ color: colors.ai, fontSize: 11 }} numberOfLines={1}>
                        {project.documentName}
                      </Text>
                    ) : null}
                    <Text variant="muted">
                      {t(STAGE_LABELS[project.stage] ?? project.stage.replaceAll("_", " "))}
                      {project.videoReady ? ` · ${t("Video ready")}` : ""}
                    </Text>
                  </Pressable>
                  <Pressable
                    onPress={() => confirmDelete(project)}
                    disabled={remove.isPending}
                    hitSlop={8}
                    style={styles.deleteButton}
                    accessibilityRole="button"
                    accessibilityLabel={`${t("Delete lesson")}: ${project.topic}`}
                  >
                    <Trash2 color={colors.bear} size={16} />
                  </Pressable>
                </View>
              ))}
            </View>
          ) : null}
        </>
      )}
    </GlassCard>
  );
}

const makeStyles = (colors: ThemeColors) =>
  StyleSheet.create({
    card: {
      gap: 14,
      padding: 16,
      borderColor: colors.ai + "42",
      backgroundColor: colors.glassFillStrong,
    },
    headingRow: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
    iconWrap: {
      width: 42,
      height: 42,
      borderRadius: 14,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.ai + "18",
      borderWidth: 1,
      borderColor: colors.ai + "42",
    },
    description: { fontSize: 12, lineHeight: 18 },
    disabledNotice: {
      gap: 4,
      borderWidth: 1,
      borderColor: colors.warning + "40",
      backgroundColor: colors.warning + "10",
      borderRadius: radii.btn,
      padding: 12,
    },
    inputRow: {
      minHeight: 50,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: 13,
      borderRadius: radii.btn,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.glassFill,
    },
    input: { flex: 1, color: colors.textPrimary, fontFamily: fonts.sans, fontSize: 14 },
    pdfPicker: {
      minHeight: 82,
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      padding: 14,
      borderRadius: radii.btn,
      borderWidth: 1,
      borderStyle: "dashed",
      borderColor: colors.ai + "66",
      backgroundColor: colors.ai + "0d",
    },
    limitRow: { flexDirection: "row", alignItems: "center", gap: 6 },
    library: { gap: 8, paddingTop: 4 },
    projectRow: {
      minHeight: 58,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderRadius: radii.btn,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.glassFill,
    },
    deleteButton: {
      width: 36,
      height: 36,
      borderRadius: 12,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.bear + "12",
    },
  });
