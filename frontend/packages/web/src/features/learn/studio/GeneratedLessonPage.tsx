import { Link, useParams } from "@tanstack/react-router";
import { AlertCircle, ArrowLeft, Loader2, Sparkles } from "lucide-react";
import { useMemo } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { useLang } from "@/hooks/use-lang";
import {
  useRecordStudioQuiz,
  useRequestStudioVideo,
  useStudioPlayback,
  useStudioProject,
} from "@/hooks/learn/use-learn-studio";
import { LessonInner } from "@/features/learn/lesson/components/LessonInner";
import type { LessonContent } from "@/lib/learn/data";

const STAGE_LABELS: Record<string, string> = {
  queued: "Preparing your lesson",
  extracting_document: "Reading and checking your private PDF",
  retrieving_sources: "Finding trusted LearnHub sources",
  generating_lesson: "Writing your lesson and quiz",
  validating: "Checking grounding and citations",
  video_queued: "Video is queued",
  writing_storyboard: "Writing the video storyboard",
  generating_audio: "Generating narration",
  rendering: "Rendering your video",
  uploading: "Preparing secure playback",
};

function LessonSkeleton({ stage }: { stage: string }) {
  return (
    <div className="mx-auto max-w-app px-3 py-6 lg:px-6">
      <div className="mb-5 flex items-center gap-2 text-sm text-ai" role="status">
        <Loader2 className="h-4 w-4 animate-spin" /> {STAGE_LABELS[stage] ?? "Creating your lesson"}
      </div>
      <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,760px)]">
        <Skeleton className="hidden h-72 rounded-card lg:block" />
        <div className="space-y-5">
          <Skeleton className="h-48 rounded-card" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-24" />
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-40" />
        </div>
      </div>
    </div>
  );
}

export function GeneratedLessonPage() {
  const { projectId } = useParams({ from: "/learn/generated/$projectId" });
  const { t } = useLang();
  const project = useStudioProject(projectId);
  const requestVideo = useRequestStudioVideo(projectId);
  const recordQuiz = useRecordStudioQuiz(projectId);
  const playback = useStudioPlayback(projectId, Boolean(project.data?.videoReady));

  const lesson = useMemo<LessonContent | null>(() => {
    const source = project.data?.studyPack?.lesson;
    if (!source) return null;
    if (!playback.data?.url) return source as LessonContent;
    return {
      ...source,
      type: "video",
      videoUrl: playback.data.url,
      captionsUrl: playback.data.captionsUrl,
      posterUrl: playback.data.posterUrl,
    } as LessonContent;
  }, [project.data?.studyPack?.lesson, playback.data]);

  if (project.isLoading || project.data?.status === "queued" || project.data?.status === "generating") {
    return <LessonSkeleton stage={project.data?.stage ?? "queued"} />;
  }

  if (project.isError || !project.data || project.data.status === "failed" || project.data.status === "unsupported") {
    return (
      <div className="mx-auto max-w-md px-4 py-20 text-center">
        <AlertCircle className="mx-auto h-9 w-9 text-warning" strokeWidth={1.5} />
        <h1 className="mt-3 text-lg font-semibold text-text-primary">
          {project.data?.status === "unsupported" ? t("We need better sources for this topic") : t("Lesson generation failed")}
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          {project.data?.errorMessage ?? t("Please try another PSX topic.")}
        </p>
        <Link to="/learn" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-btn bg-bull px-4 text-sm font-semibold text-bull-foreground">
          <ArrowLeft className="h-4 w-4" /> {t("Back to Learn Hub")}
        </Link>
      </div>
    );
  }

  if (!lesson || !project.data.studyPack) return <LessonSkeleton stage={project.data.stage} />;

  const videoGenerating = ["video_queued", "writing_storyboard", "generating_audio", "rendering", "uploading"].includes(project.data.stage);

  return (
    <>
      {videoGenerating && (
        <div className="sticky top-[var(--header-h)] z-30 flex items-center justify-center gap-2 border-b border-ai/20 bg-ai/10 px-3 py-2 text-xs font-medium text-ai" role="status">
          <Sparkles className="h-3.5 w-3.5 animate-pulse" /> {t(STAGE_LABELS[project.data.stage] ?? "Generating video")}
        </div>
      )}
      {project.data.stage === "video_failed" && (
        <div className="border-b border-warning/25 bg-warning/10 px-3 py-2 text-center text-xs font-medium text-warning" role="alert">
          {t(project.data.errorMessage ?? "The lesson is ready, but the video could not be generated. You can retry.")}
        </div>
      )}
      <LessonInner
        key={lesson.id}
        lesson={lesson}
        studyPack={project.data.studyPack}
        onGenerateVideo={() => requestVideo.mutate()}
        videoGenerating={videoGenerating || requestVideo.isPending}
        onPracticeFinish={(correct, total) => recordQuiz.mutate({ correct, total, answers: [] })}
      />
    </>
  );
}
