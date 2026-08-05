import type { StudioPlayback, StudioProject } from "@nafaiq/shared";
import { userGet, userPost } from "./api";

export const fetchStudioProject = (projectId: string) =>
  userGet<StudioProject>(`/api/learn/studio/projects/${encodeURIComponent(projectId)}`);

export const fetchStudioPlayback = (projectId: string) =>
  userGet<StudioPlayback>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/video/playback`,
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
  input: { message: string; history: Array<{ role: "user" | "assistant"; content: string }>; lang: "en" | "ur" },
) =>
  userPost<{ answer: string | null; sources: string[] }>(
    `/api/learn/studio/projects/${encodeURIComponent(projectId)}/chat`,
    input,
  );
