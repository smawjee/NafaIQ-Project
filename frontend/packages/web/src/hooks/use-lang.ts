import { useSyncExternalStore, useCallback } from "react";
import { LEARN_UR } from "@/lib/learn/ur";
import { UR } from "@/lib/lang-ur";

export type Lang = "en" | "ur";

const STORAGE_KEY = "nafaiq-app-lang";
const listeners = new Set<() => void>();
let current: Lang = readStored();

function readStored(): Lang {
  if (typeof window === "undefined") return "en";
  return window.localStorage.getItem(STORAGE_KEY) === "ur" ? "ur" : "en";
}

function setStore(lang: Lang) {
  current = lang;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, lang);
  }
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function translate(lang: Lang, key: string): string {
  if (lang === "en") return key;
  // Hand-curated UI dictionary takes priority, then generated Learn Hub content.
  return UR[key] ?? LEARN_UR[key] ?? key;
}

/** Current app language, readable outside React (e.g. number formatters). */
export function getCurrentLang(): Lang {
  return current;
}

/** Numbers stay in Western digits app-wide — return input unchanged. */
export function toUrduDigits(input: string): string {
  return input;
}

/** Numbers stay in Western digits regardless of language. */
export function localizeDigits(input: string): string {
  return input;
}

/**
 * App language (English / Urdu) shared across components and persisted.
 * Scoped to the authenticated app — the landing page stays English.
 */
export function useLang() {
  const lang = useSyncExternalStore(
    subscribe,
    () => current,
    () => "en" as Lang,
  );

  const setLang = useCallback((l: Lang) => setStore(l), []);
  const t = useCallback((key: string) => translate(lang, key), [lang]);

  return { lang, setLang, t, isUrdu: lang === "ur" };
}
