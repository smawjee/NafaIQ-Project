import { useLocalSearchParams, useRouter } from "expo-router";
import { useMemo } from "react";
import { ActivityIndicator, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Text } from "@/components/ui";
import {
  useRecordStudioQuiz,
  useStudioPlayback,
  useStudioProject,
} from "@/hooks/queries/use-learn-studio";
import { useTheme } from "@/hooks/use-theme";
import { ArrowLeft, Sparkles, TriangleAlert } from "@/lib/icons";
import type { LessonContent } from "@nafaiq/shared";
import { LessonExperience } from "@/app/(tabs)/learn/lesson/[id]";

const stages: Record<string, string> = {
  queued: "Preparing your lesson",
  extracting_document: "Reading and checking your private PDF",
  retrieving_sources: "Finding trusted LearnHub sources",
  generating_lesson: "Writing your lesson and quiz",
  validating: "Checking grounding and citations",
};

export default function GeneratedLessonScreen() {
  const { projectId = "" } = useLocalSearchParams<{ projectId: string }>();
  const { colors } = useTheme();
  const router = useRouter();
  const project = useStudioProject(projectId);
  const playback = useStudioPlayback(
    projectId,
    Boolean(project.data?.videoReady),
  );
  const attempt = useRecordStudioQuiz(projectId);

  const lesson = useMemo<LessonContent | null>(() => {
    const value = project.data?.studyPack?.lesson;
    if (!value) return null;
    return playback.data?.url
      ? {
          ...value,
          type: "video",
          videoUrl: playback.data.url,
          captionsUrl: playback.data.captionsUrl,
          posterUrl: playback.data.posterUrl,
        }
      : value;
  }, [project.data?.studyPack?.lesson, playback.data]);

  if (
    project.isLoading ||
    project.data?.status === "queued" ||
    project.data?.status === "generating"
  ) {
    return (
      <GlassScreen>
        <SafeAreaView style={styles.center}>
          <ActivityIndicator color={colors.ai} size="large" />
          <View style={styles.statusRow} accessibilityRole="text">
            <Sparkles color={colors.ai} size={16} />
            <Text variant="secondary">
              {stages[project.data?.stage ?? "queued"] ??
                "Creating your lesson"}
            </Text>
          </View>
        </SafeAreaView>
      </GlassScreen>
    );
  }

  if (
    !lesson ||
    !project.data?.studyPack ||
    project.isError ||
    project.data.status === "failed" ||
    project.data.status === "unsupported"
  ) {
    return (
      <GlassScreen>
        <SafeAreaView style={styles.center}>
          <TriangleAlert color={colors.warning} size={34} />
          <Text variant="title">
            {project.data?.status === "unsupported"
              ? "More trusted sources are needed"
              : "Lesson unavailable"}
          </Text>
          <Text variant="secondary" style={styles.centerText}>
            {project.data?.errorMessage ??
              "Try another PSX topic from LearnHub."}
          </Text>
          <Pressable
            onPress={() => router.back()}
            style={[styles.backButton, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="Back to LearnHub"
          >
            <ArrowLeft color={colors.textPrimary} size={18} />
            <Text>Back to LearnHub</Text>
          </Pressable>
        </SafeAreaView>
      </GlassScreen>
    );
  }

  return (
    <LessonExperience
      lesson={lesson}
      lessonId={lesson.id}
      practice
      studioProjectId={projectId}
      notes={project.data.studyPack.notes}
      keyTerms={project.data.studyPack.keyTerms}
      suggestedTopics={project.data.studyPack.suggestedTopics}
      sources={project.data.studyPack.lesson.sources}
      onPracticeFinish={(correct, total) => attempt.mutate({ correct, total })}
    />
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    padding: 24,
  },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  centerText: { textAlign: "center" },
  backButton: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 16,
  },
});
