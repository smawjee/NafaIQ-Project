import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateStudioProjectInput } from "@nafaiq/shared";
import {
  createStudioPdfProject,
  createStudioProject,
  deleteStudioProject,
  fetchStudioPlayback,
  fetchStudioProject,
  fetchStudioProjects,
  fetchStudioStatus,
  recordStudioQuiz,
  requestStudioVideo,
  type MobileStudioPdfInput,
} from "@/lib/learn-studio";

const VIDEO_STAGES = [
  "video_queued",
  "writing_storyboard",
  "generating_audio",
  "rendering",
  "uploading",
];

export function useStudioStatus(enabled = true) {
  return useQuery({
    queryKey: ["learn", "studio", "status"],
    queryFn: fetchStudioStatus,
    enabled,
    staleTime: 60_000,
    retry: false,
  });
}

export function useStudioProjects(enabled = true) {
  return useQuery({
    queryKey: ["learn", "studio", "projects"],
    queryFn: fetchStudioProjects,
    enabled,
    staleTime: 15_000,
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
      return status === "queued" || status === "generating" || VIDEO_STAGES.includes(stage ?? "")
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
    mutationFn: (input: MobileStudioPdfInput) => createStudioPdfProject(input),
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
