import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateStudioPdfProjectInput, CreateStudioProjectInput } from "@nafaiq/shared";
import {
  createStudioProject,
  createStudioPdfProject,
  deleteStudioProject,
  fetchStudioPlayback,
  fetchStudioProject,
  fetchStudioProjects,
  fetchStudioStatus,
  recordStudioQuiz,
  requestStudioVideo,
} from "@/lib/learn/studio-client";

export function useStudioStatus(enabled = true) {
  return useQuery({
    queryKey: ["learn", "studio", "status"],
    queryFn: fetchStudioStatus,
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useStudioProjects(enabled = true) {
  return useQuery({
    queryKey: ["learn", "studio", "projects"],
    queryFn: fetchStudioProjects,
    enabled,
  });
}

export function useStudioProject(projectId: string) {
  return useQuery({
    queryKey: ["learn", "studio", "project", projectId],
    queryFn: () => fetchStudioProject(projectId),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const stage = query.state.data?.stage;
      return status === "queued" ||
        status === "generating" ||
        [
          "video_queued",
          "writing_storyboard",
          "generating_audio",
          "rendering",
          "uploading",
        ].includes(stage ?? "")
        ? 2_000
        : false;
    },
  });
}

export function useCreateStudioProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateStudioProjectInput) => createStudioProject(input),
    onSuccess: () => client.invalidateQueries({ queryKey: ["learn", "studio", "projects"] }),
  });
}

export function useCreateStudioPdfProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateStudioPdfProjectInput) => createStudioPdfProject(input),
    onSuccess: () => client.invalidateQueries({ queryKey: ["learn", "studio", "projects"] }),
  });
}

export function useDeleteStudioProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => deleteStudioProject(projectId),
    onSuccess: () => client.invalidateQueries({ queryKey: ["learn", "studio", "projects"] }),
  });
}

export function useRequestStudioVideo(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => requestStudioVideo(projectId),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["learn", "studio", "project", projectId] }),
  });
}

export function useRecordStudioQuiz(projectId: string) {
  return useMutation({
    mutationFn: (score: { correct: number; total: number; answers: Array<number | null> }) =>
      recordStudioQuiz(projectId, score),
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
