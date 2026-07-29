import { useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useLearnSearch } from "@/hooks/learn/use-learn-search";
import type { ApiLearnSearchResult } from "@/lib/psx/client";

/** Badge label + tokenized colors per result source. Labels go through t(). */
const SOURCE_BADGE: Record<
  ApiLearnSearchResult["source_type"],
  { label: string; className: string }
> = {
  lesson_section: { label: "Lesson", className: "bg-bull/10 text-bull" },
  lesson_overview: { label: "Lesson", className: "bg-bull/10 text-bull" },
  glossary_term: { label: "Glossary", className: "bg-ai/10 text-ai" },
  quiz_explanation: { label: "Quiz", className: "bg-warning/10 text-warning" },
  learning_path: { label: "Path", className: "bg-elevated text-text-secondary" },
};

/**
 * LearnHub content search over lessons, glossary terms, quiz explanations and
 * learning paths (RAG-backed). Interaction mirrors StockSearchBox: debounced
 * input, up/down/enter/escape keyboard nav, floating dropdown, loading and
 * empty states. Selecting a result navigates to the matching lesson/section.
 */
export function LearnSearchBox({ className }: { className?: string }) {
  const navigate = useNavigate();
  const { lang, t } = useLang();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const { results, loading, isEmpty, hasQuery } = useLearnSearch(query, lang);
  const listRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => setActive(0), [query]);

  // keep the highlighted row in view
  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  // outside click closes the dropdown
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function choose(r: ApiLearnSearchResult) {
    if (
      (r.source_type === "lesson_section" || r.source_type === "quiz_explanation") &&
      r.lesson_id
    ) {
      navigate({
        to: "/learn/lesson/$id",
        params: { id: r.lesson_id },
        ...(r.section_id ? { hash: r.section_id } : {}),
      });
    } else if (
      (r.source_type === "lesson_overview" || r.source_type === "learning_path") &&
      r.lesson_id
    ) {
      navigate({ to: "/learn/lesson/$id", params: { id: r.lesson_id } });
    } else {
      // glossary_term / a path with no lesson. The box only mounts inside
      // LearnHub, which IS /learn — navigating there is a no-op, so the click
      // did nothing. Scroll to the glossary section instead; the id is on the
      // hub's glossary <section>.
      document.getElementById("learn-glossary")?.scrollIntoView({ behavior: "smooth" });
    }
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const r = results[active];
      if (r) choose(r);
    } else if (e.key === "Escape") {
      if (query) setQuery("");
      else setOpen(false);
      e.currentTarget.blur();
    }
  }

  const showResults = open && (hasQuery || loading);

  return (
    <div ref={rootRef} className={cn("relative flex flex-col", className)}>
      <div className="relative">
        <Search className="pointer-events-none absolute start-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setOpen(true)}
          aria-label={t("Search LearnHub…")}
          placeholder={t("Search LearnHub…")}
          className="h-9 w-full rounded-[8px] border border-border bg-surface ps-8 pe-3 text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-bull"
        />
      </div>

      {showResults && (
        <div className="absolute top-11 z-50 w-full overflow-hidden rounded-[12px] border border-border bg-surface px-1 shadow-2xl">
          <div ref={listRef} className="max-h-72 overflow-y-auto py-1">
            {loading ? (
              <div className="flex items-center justify-center gap-2 py-6 text-xs text-text-muted">
                <Loader2 className="h-4 w-4 animate-spin" /> {t("Searching…")}
              </div>
            ) : isEmpty ? (
              <div className="py-6 text-center text-xs text-text-muted">
                {t("No results found")}
              </div>
            ) : (
              results.map((r, i) => {
                const badge = SOURCE_BADGE[r.source_type];
                const urduSnippet = lang === "ur" && r.snippet_ur != null;
                const snippet = urduSnippet ? r.snippet_ur : r.snippet_en;
                return (
                  <button
                    key={`${r.source_type}-${r.lesson_id}-${r.section_id ?? ""}-${i}`}
                    data-idx={i}
                    type="button"
                    onMouseEnter={() => setActive(i)}
                    onClick={() => choose(r)}
                    className={cn(
                      "block w-full rounded-[6px] px-2 py-1.5 text-start transition-colors",
                      i === active ? "bg-hover" : "hover:bg-hover",
                    )}
                  >
                    <span className="flex items-center gap-2">
                      <span
                        className={cn(
                          "shrink-0 rounded-[4px] px-1.5 py-0.5 text-[10px] font-medium",
                          badge.className,
                        )}
                      >
                        {t(badge.label)}
                      </span>
                      <span className="truncate text-sm font-medium text-text-primary">
                        {t(r.title)}
                      </span>
                      {r.heading ? (
                        <span className="truncate text-[11px] text-text-secondary">
                          {t(r.heading)}
                        </span>
                      ) : null}
                    </span>
                    {/* Snippets are raw backend text — never through t(). */}
                    <span
                      dir={urduSnippet ? "rtl" : undefined}
                      className={cn(
                        "mt-0.5 line-clamp-2 block text-[11px] leading-relaxed text-text-muted",
                        urduSnippet && "font-urdu",
                      )}
                    >
                      {snippet}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
