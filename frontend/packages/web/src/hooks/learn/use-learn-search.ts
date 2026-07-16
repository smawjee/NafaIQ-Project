import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchLearnRelated,
  fetchLearnStatus,
  searchLearn,
  searchLearnGlossary,
} from "@/lib/psx/client";
import type {
  ApiLearnRelated,
  ApiLearnSearchResult,
  ApiLearnStatus,
} from "@/lib/psx/client";
import type { Lang } from "@/hooks/use-lang";

/** Timer debounce — the Learn search hits the network, unlike the client-side
 * stock search which gets away with useDeferredValue. */
function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * Feature flag for the LearnHub RAG search. Queried once per session; any
 * error (backend not deployed yet → 404/503) reads as disabled so the UI
 * simply doesn't render the search box.
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
 * Debounced LearnHub content search (lessons, glossary, quizzes, paths).
 * Only fires when the RAG feature flag is on and the query has 2+ chars.
 * Errors are swallowed into an empty result list — search never shows an
 * error state.
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
    // Keep showing the previous results while the next query is in flight.
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
 * Related lessons for the current lesson, by content similarity.
 *
 * Server-side this is a precomputed lookup (rebuilt at ingest), so it is cheap
 * enough to fire on every lesson page. Errors and a disabled flag both read as
 * "no related lessons", and the caller renders nothing — never an error state
 * on a reading page.
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
 * Semantic glossary lookup. Layered deliberately: the hub keeps its instant
 * client-side substring filter and only consults this when that finds nothing,
 * so typing stays responsive and the network is spared — the API is what turns
 * "what do I call the thing where the market drops" into Bear Market.
 */
export function useGlossarySearch(query: string, lang: Lang, active: boolean): {
  results: ApiLearnSearchResult[];
  loading: boolean;
} {
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
