/**
 * Keep the browser tab title in the app's language.
 *
 * Route `head()` titles are evaluated during route matching on both the server
 * and the client. Translating them there would emit English on the server and
 * Urdu after hydration, which is a `<title>` mismatch React reports as a
 * hydration error. Setting `document.title` from an effect instead runs only
 * after hydration, so the served markup stays byte-identical — and English
 * remains what crawlers index, which is what we want for SEO.
 */
import { useEffect } from "react";
import { useRouterState } from "@tanstack/react-router";
import { useLang } from "@/hooks/use-lang";

/**
 * The dictionary key a document title actually looks up.
 *
 * Titles read "Dashboard — NafaIQ": only the descriptive part is translated,
 * so one entry per page is enough and the brand never has to be repeated.
 * Exported so the i18n coverage test checks the same key this resolves at
 * runtime — otherwise the test would demand entries for the full strings.
 */
export function documentTitleKey(title: string): string {
  // Both an em dash and a hyphen are used across the route files.
  const match = /^(.*?)\s+[—-]\s+(NafaIQ.*)$/.exec(title);
  return match ? match[1] : title;
}

function translateTitle(title: string, t: (k: string) => string): string {
  const match = /^(.*?)\s+[—-]\s+(NafaIQ.*)$/.exec(title);
  if (!match) return t(title);
  return `${t(match[1])} — ${match[2]}`;
}

export function useDocumentTitle() {
  const { t, lang } = useLang();
  // The deepest match that declares a title wins, matching how the head tags
  // themselves resolve.
  const title = useRouterState({
    select: (s) => {
      for (let i = s.matches.length - 1; i >= 0; i--) {
        const meta = s.matches[i].meta;
        const entry = meta?.find((m) => typeof m?.title === "string");
        if (entry?.title) return entry.title as string;
      }
      return undefined;
    },
  });

  useEffect(() => {
    if (!title) return;
    document.title = translateTitle(title, t);
    // `lang` is listed so the title re-resolves on a language switch even
    // though `t`'s identity already changes with it.
  }, [title, t, lang]);
}
