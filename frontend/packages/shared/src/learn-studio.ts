import type { LessonContent } from "./lesson-content";

export type StudioLanguage = "en" | "ur";
export type StudioLevel = "beginner" | "intermediate" | "advanced";
export type StudioProjectStatus = "queued" | "generating" | "ready" | "unsupported" | "failed";

export interface StudioSource {
  sourceId: string;
  title: string;
  heading?: string | null;
  lessonId?: string | null;
}

export interface StudioFlashcard {
  front: string;
  back: string;
}

export interface GeneratedLessonContent extends LessonContent {
  origin: "generated";
  language: StudioLanguage;
  sources: StudioSource[];
  projectId: string;
  videoStatus: string;
  rewardMode: "practice";
  generatedAt?: string | null;
  sourceKind?: "topic" | "pdf";
  documentName?: string | null;
}

export interface StudioStudyPack {
  lesson: GeneratedLessonContent;
  notes: string[];
  keyTerms: string[];
  flashcards: StudioFlashcard[];
  suggestedTopics: string[];
}

export interface StudioProject {
  id: string;
  topic: string;
  language: StudioLanguage;
  level: StudioLevel;
  targetMinutes: number;
  sourceKind?: "topic" | "pdf";
  documentName?: string | null;
  documentPageCount?: number | null;
  status: StudioProjectStatus;
  stage: string;
  errorCode?: string | null;
  errorMessage?: string | null;
  bestScore: number;
  studyPack?: StudioStudyPack | null;
  videoReady: boolean;
  videoDurationSeconds?: number | null;
  createdAt: string;
}

export interface StudioProjectsResponse {
  projects: StudioProject[];
}

export interface StudioPlayback {
  url: string;
  captionsUrl?: string | null;
  posterUrl?: string | null;
  durationSeconds?: number | null;
  expiresIn: number;
}

export interface CreateStudioProjectInput {
  topic: string;
  lang: StudioLanguage;
  level: StudioLevel;
  targetMinutes?: number;
}

export interface CreateStudioPdfProjectInput {
  file: Blob;
  filename?: string;
  topic?: string;
  lang: StudioLanguage;
  level: StudioLevel;
  targetMinutes?: number;
}
