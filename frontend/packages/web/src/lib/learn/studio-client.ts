import type {
  CreateStudioProjectInput,
  CreateStudioPdfProjectInput,
  StudioPlayback,
  StudioProject,
  StudioProjectsResponse,
} from "@nafaiq/shared";
import { userDelete, userGet, userPost, userPostForm } from "@/lib/psx/client";

export const createStudioProject = (input: CreateStudioProjectInput) =>
  userPost<StudioProject>("/api/learn/studio/projects", input);

export const createStudioPdfProject = (input: CreateStudioPdfProjectInput) => {
  const body = new FormData();
  body.append(
    "file",
    input.file,
    input.filename ?? (input.file instanceof File ? input.file.name : "document.pdf"),
  );
  body.append("topic", input.topic ?? "");
  body.append("lang", input.lang);
  body.append("level", input.level);
  body.append("targetMinutes", String(input.targetMinutes ?? 4));
  return userPostForm<StudioProject>("/api/learn/studio/projects/pdf", body);
};

export const fetchStudioStatus = () =>
  userGet<{
    enabled: boolean;
    packDailyLimit: number;
    videoDailyLimit: number;
    pdfEnabled?: boolean;
    pdfMaxBytes?: number;
    pdfMaxPages?: number;
  }>("/api/learn/studio/status");

export const fetchStudioProjects = () =>
  userGet<StudioProjectsResponse>("/api/learn/studio/projects");

export const fetchStudioProject = (projectId: string) =>
  userGet<StudioProject>(`/api/learn/studio/projects/${encodeURIComponent(projectId)}`);

export const deleteStudioProject = (projectId: string) =>
  userDelete<void>(`/api/learn/studio/projects/${encodeURIComponent(projectId)}`);

export const requestStudioVideo = (projectId: string) =>
  userPost<StudioProject & { videoQueued: boolean }>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/video`,
    {},
  );

export const recordStudioQuiz = (
  projectId: string,
  input: { correct: number; total: number; answers: Array<number | null> },
) =>
  userPost<{ bestScore: number }>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/quiz-attempts`,
    input,
  );

export const fetchStudioPlayback = (projectId: string) =>
  userGet<StudioPlayback>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/video/playback`,
  );

export const askStudioTutor = (
  projectId: string,
  input: {
    message: string;
    history: Array<{ role: "user" | "assistant"; content: string }>;
    lang: "en" | "ur";
  },
) =>
  userPost<{ answer: string | null; sources: string[] }>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/chat`,
    input,
  );
