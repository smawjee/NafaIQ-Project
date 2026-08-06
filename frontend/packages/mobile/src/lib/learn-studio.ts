import type {
  CreateStudioProjectInput,
  StudioPlayback,
  StudioProject,
  StudioProjectsResponse,
} from "@nafaiq/shared";
import { userDelete, userGet, userPost, userUpload } from "./api";

export interface StudioStatus {
  enabled: boolean;
  packDailyLimit: number;
  videoDailyLimit: number;
  pdfEnabled: boolean;
  pdfMaxBytes: number;
  pdfMaxPages: number;
}

export interface MobileStudioPdfInput {
  uri: string;
  filename: string;
  mimeType?: string | null;
  size?: number | null;
  topic?: string;
  lang: "en" | "ur";
  level: "beginner" | "intermediate" | "advanced";
  targetMinutes?: number;
}

export const fetchStudioStatus = () =>
  userGet<StudioStatus>("/api/learn/studio/status");

export const fetchStudioProjects = () =>
  userGet<StudioProjectsResponse>("/api/learn/studio/projects");

export const createStudioProject = (input: CreateStudioProjectInput) =>
  userPost<StudioProject>("/api/learn/studio/projects", input);

export const createStudioPdfProject = (input: MobileStudioPdfInput) => {
  const form = new FormData();
  form.append(
    "file",
    {
      uri: input.uri,
      name: input.filename,
      type: input.mimeType || "application/pdf",
    } as unknown as Blob,
  );
  form.append("topic", input.topic?.trim() ?? "");
  form.append("lang", input.lang);
  form.append("level", input.level);
  form.append("targetMinutes", String(input.targetMinutes ?? 4));
  return userUpload<StudioProject>("/api/learn/studio/projects/pdf", form);
};

export const fetchStudioProject = (projectId: string) =>
  userGet<StudioProject>(`/api/learn/studio/projects/${encodeURIComponent(projectId)}`);

export const fetchStudioPlayback = (projectId: string) =>
  userGet<StudioPlayback>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/video/playback`,
  );

export const deleteStudioProject = (projectId: string) =>
  userDelete<void>(`/api/learn/studio/projects/${encodeURIComponent(projectId)}`);

export const requestStudioVideo = (projectId: string) =>
  userPost<StudioProject & { videoQueued: boolean }>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/video`,
    {},
  );

export const recordStudioQuiz = (
  projectId: string,
  correct: number,
  total: number,
) =>
  userPost<{ bestScore: number }>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/quiz-attempts`,
    { correct, total, answers: [] },
  );

export const askStudioTutor = (
  projectId: string,
  input: { message: string; history: { role: "user" | "assistant"; content: string }[]; lang: "en" | "ur" },
) =>
  userPost<{ answer: string | null; sources: string[] }>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/chat`,
    input,
  );
