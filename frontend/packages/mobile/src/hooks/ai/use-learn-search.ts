// Learn Hub RAG search: status flag, content search, glossary search, related
// lessons. Mobile twin of web's src/hooks/learn/use-learn-search.ts.
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { type Lang } from "@/hooks/use-lang";
import { publicGet } from "@/lib/api";

// === API types + fetchers (public routes) ===

export interface ApiLearnStatus {
  enabled: boolean;
}

export interface ApiLearnSearchResult {
  /** null on glossary_term rows — they belong to no lesson. */
  lesson_id: string | null;
  section_id: string | null;
  source_type:
    | "lesson_section"
    | "lesson_overview"
    | "glossary_term"
    | "quiz_explanation"
    | "learning_path";
  title: string;
  heading: string | null;
  snippet_en: string;
  snippet_ur: string | null;
  score: number;
}

interface ApiLearnSearchResponse {
  results: ApiLearnSearchResult[];
}

export interface ApiLearnRelated {
  lesson_id: string;
  score: number;
}

interface ApiLearnRelatedResponse {
  results: ApiLearnRelated[];
}

function fetchLearnStatus(): Promise<ApiLearnStatus> {
  return publicGet<ApiLearnStatus>("/api/learn/status");
}

function searchLearn(q: string, lang: Lang, limit = 8): Promise<ApiLearnSearchResponse> {
  const params = new URLSearchParams({ q, lang, limit: String(limit) });
  return publicGet<ApiLearnSearchResponse>(`/api/learn/search?${params.toString()}`);
}

function searchLearnGlossary(q: string, lang: Lang, limit = 5): Promise<ApiLearnSearchResponse> {
  const params = new URLSearchParams({ q, lang, limit: String(limit) });
  return publicGet<ApiLearnSearchResponse>(`/api/learn/glossary/search?${params.toString()}`);
}

function fetchLearnRelated(lessonId: string, limit = 4): Promise<ApiLearnRelatedResponse> {
  const params = new URLSearchParams({ lesson_id: lessonId, limit: String(limit) });
  return publicGet<ApiLearnRelatedResponse>(`/api/learn/related?${params.toString()}`);
}

// === Hooks ===

/** Timer debounce — the Learn search hits the network. */
function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * Feature flag for the LearnHub RAG search. Queried once per session; any error
 * (backend not deployed yet → 404/503) reads as disabled so the UI simply
 * doesn't render the search box.
 */
export function useLearnRagStatus(): { enabled: boolean } {
  const { data } = useQuery<ApiLearnStatus>({
    queryKey: ["learn", "rag-status"],
    queryFn: () => fetchLearnStatus().catch(() => ({ enabled: false })),
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });
  return { enabled: data?.enabled ?? false };
}

export interface UseLearnSearch {
  results: ApiLearnSearchResult[];
  loading: boolean;
  isEmpty: boolean;
  hasQuery: boolean;
}

/**
 * Debounced LearnHub content search (lessons, glossary, quizzes, paths). Only
 * fires when the RAG flag is on and the query has 2+ chars. Errors swallow into
 * an empty result list — search never shows an error state.
 */
export function useLearnSearch(query: string, lang: Lang): UseLearnSearch {
  const { enabled: ragEnabled } = useLearnRagStatus();
  const debounced = useDebouncedValue(query.trim(), 250);
  const enabled = ragEnabled && debounced.length >= 2;

  const { data, isFetching } = useQuery<ApiLearnSearchResult[]>({
    queryKey: ["learn", "search", lang, debounced],
    queryFn: () =>
      searchLearn(debounced, lang)
        .then((r) => r.results)
        .catch(() => []),
    enabled,
    retry: false,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

  const results = enabled ? (data ?? []) : [];
  const loading = enabled && isFetching && data === undefined;
  return {
    results,
    loading,
    isEmpty: enabled && !isFetching && results.length === 0,
    hasQuery: enabled,
  };
}

/**
 * Related lessons for the current lesson, by content similarity. Cheap
 * precomputed lookup server-side. Errors and a disabled flag both read as "no
 * related lessons".
 */
export function useRelatedLessons(lessonId: string, limit = 4): ApiLearnRelated[] {
  const { enabled } = useLearnRagStatus();
  const { data } = useQuery<ApiLearnRelated[]>({
    queryKey: ["learn", "related", lessonId, limit],
    queryFn: () =>
      fetchLearnRelated(lessonId, limit)
        .then((r) => r.results)
        .catch(() => []),
    enabled: enabled && Boolean(lessonId),
    retry: false,
    staleTime: 5 * 60_000,
  });
  return data ?? [];
}

/**
 * Semantic glossary lookup. Layered: the hub keeps its instant client-side
 * substring filter and only consults this when active + 2+ chars.
 */
export function useGlossarySearch(
  query: string,
  lang: Lang,
  active: boolean,
): { results: ApiLearnSearchResult[]; loading: boolean } {
  const { enabled: ragEnabled } = useLearnRagStatus();
  const debounced = useDebouncedValue(query.trim(), 250);
  const enabled = ragEnabled && active && debounced.length >= 2;

  const { data, isFetching } = useQuery<ApiLearnSearchResult[]>({
    queryKey: ["learn", "glossary-search", lang, debounced],
    queryFn: () =>
      searchLearnGlossary(debounced, lang)
        .then((r) => r.results)
        .catch(() => []),
    enabled,
    retry: false,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

  return {
    results: enabled ? (data ?? []) : [],
    loading: enabled && isFetching && data === undefined,
  };
}
