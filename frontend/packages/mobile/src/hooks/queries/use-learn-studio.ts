import { useMutation, useQuery } from "@tanstack/react-query";
import {
  fetchStudioPlayback,
  fetchStudioProject,
  recordStudioQuiz,
} from "@/lib/learn-studio";

export function useStudioProject(projectId: string) {
  return useQuery({
    queryKey: ["learn", "studio", "project", projectId],
    queryFn: () => fetchStudioProject(projectId),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const stage = query.state.data?.stage;
      return status === "queued" || status === "generating" || ["video_queued", "writing_storyboard", "generating_audio", "rendering", "uploading"].includes(stage ?? "")
        ? 2_000
        : false;
    },
  });
}

export function useStudioPlayback(projectId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["learn", "studio", "playback", projectId],
    queryFn: () => fetchStudioPlayback(projectId),
    enabled,
    staleTime: 12 * 60 * 1000,
  });
}

export function useRecordStudioQuiz(projectId: string) {
  return useMutation({
    mutationFn: ({ correct, total }: { correct: number; total: number }) =>
      recordStudioQuiz(projectId, correct, total),
  });
}
