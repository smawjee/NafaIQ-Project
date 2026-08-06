/**
 * i18n coverage guard.
 *
 * `translate()` falls back to the English key when a string is missing, so an
 * untranslated string is invisible in English and silently English in Urdu.
 * This walks the source the way a translator would and fails on anything
 * user-facing that has no Urdu entry — that is the only way the gap shows up
 * before a user sees it.
 */
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { UR } from "@/lib/lang-ur";
import { LEARN_UR } from "@/lib/learn/ur";
import { documentTitleKey } from "@/hooks/use-document-title";

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const DICT: Record<string, string> = { ...LEARN_UR, ...UR };

/**
 * Intentionally untranslated, with the reason. Anything not on this list and
 * not in the dictionary is a bug.
 */
const ALLOWED_ENGLISH = new Set([
  "Esc", // keyboard key legend
  "flags.write", // permission slug, rendered as code
  "learn.write", // permission slug, rendered as code
  "PROCESS_ROLE", // environment variable name
  "usmankhalidj15@gmail.com", // literal support address
  "+50 XP",
  "+PKR 96,864",
  "-PKR 102,722 eroded", // numerals, not prose
  "IQ", // the second half of the NafaIQ wordmark
  "LOTCHEM", // PSX ticker in the landing ticker strip
  "NafaIQ", // brand wordmark
  "10%",
  "25%",
  "75%",
  "80%",
  "90%",
  "100%", // preset percentages
]);

/**
 * Dictionary entries whose Urdu value is legitimately identical to the English
 * key: index names, tickers and formulas are written the same in both.
 */
const SAME_IN_BOTH = new Set([
  "RSI",
  "RSI = 100 - [100 / (1 + RS)]",
  "KMI-30",
  "KSE-30",
  "PSX + NCCPL",
]);

/** Directories excluded from the sweep, with the reason. */
const SKIP_PREFIXES = [
  "components/ui/", // shadcn primitives; copy comes from callers
  "routeTree.gen.ts", // generated
  "lib/lang-ur.ts",
  "lib/learn/ur.ts",
  "mocks/",
];

const OBJ_KEYS = [
  "header",
  "label",
  "title",
  "description",
  "hint",
  "placeholder",
  "heading",
  "subtitle",
  "tip",
  "empty",
  "caption",
  "sub",
  "helpText",
  "blurb",
  "summary",
  "question",
  "answer",
  "explanation",
  "mobile",
  "short",
  "long",
  "cta",
  "body",
  "text",
  "name",
];
const JSX_PROPS = [
  "placeholder",
  "title",
  "label",
  "aria-label",
  "alt",
  "description",
  "hint",
  "sub",
  "info",
  "emptyText",
  "tooltip",
  "heading",
  "subtitle",
  "confirmLabel",
  "cancelLabel",
];

/** Single code-ish token (identifier, path, url, acronym) — not prose. */
const CODE_TOKEN =
  /^(https?:|\/|#|[a-z-]+\/[a-z-]+$|[a-z]+([A-Z][a-z]+)+$|[a-z_]+$|\d|[A-Z]{1,6}$|PKR|NafaIQ|PSX)/;

function walk(dir: string, out: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (["node_modules", "__tests__", ".output", "dist"].includes(e.name)) continue;
      walk(p, out);
    } else if (/\.(tsx|ts)$/.test(e.name) && !/\.(test|spec)\.tsx?$/.test(e.name)) {
      out.push(p);
    }
  }
  return out;
}

function collectGaps(): Map<string, string> {
  const gaps = new Map<string, string>();
  const objRe = new RegExp(
    `(^|[\\s{,(\\[])(${OBJ_KEYS.join("|")}):\\s*"((?:\\\\.|[^"\\\\])*)"`,
    "gm",
  );
  const propRe = new RegExp(`\\s(${JSX_PROPS.join("|")})="((?:\\\\.|[^"\\\\])*)"`, "g");
  const tRe = /\bt\(\s*(["'`])((?:\\.|(?!\1)[^\\])*)\1\s*[),]/g;
  const jsxRe = />([^<>{}]+)<\//g;

  const add = (raw: string, where: string) => {
    const s = raw.replace(/\s+/g, " ").trim();
    if (!s || s.length < 2 || !/[A-Za-z]{2,}/.test(s)) return;
    if (s in DICT || ALLOWED_ENGLISH.has(s)) return;
    if (!/\s/.test(s) && CODE_TOKEN.test(s)) return;
    if (!gaps.has(s)) gaps.set(s, where);
  };

  for (const file of walk(SRC)) {
    const rel = path.relative(SRC, file).replace(/\\/g, "/");
    if (SKIP_PREFIXES.some((p) => rel.startsWith(p))) continue;
    const src = fs.readFileSync(file, "utf8");
    const lineOf = (i: number) => src.slice(0, i).split("\n").length;

    let m: RegExpExecArray | null;
    objRe.lastIndex = 0;
    while ((m = objRe.exec(src))) {
      // Meta *names* ("theme-color", "twitter:image") are HTML attributes, not
      // copy, so they are skipped. Route <head> titles ARE checked, but against
      // the key useDocumentTitle() actually looks up — the page part, not the
      // full "Page — NafaIQ" string.
      if (rel.startsWith("routes/") && m[2] === "name") continue;
      const value = rel.startsWith("routes/") && m[2] === "title" ? documentTitleKey(m[3]) : m[3];
      add(value, `${rel}:${lineOf(m.index)}`);
    }
    propRe.lastIndex = 0;
    while ((m = propRe.exec(src))) add(m[2], `${rel}:${lineOf(m.index)}`);
    tRe.lastIndex = 0;
    while ((m = tRe.exec(src))) add(m[2], `${rel}:${lineOf(m.index)}`);
    if (file.endsWith(".tsx")) {
      jsxRe.lastIndex = 0;
      while ((m = jsxRe.exec(src))) add(m[1], `${rel}:${lineOf(m.index)}`);
    }
  }
  return gaps;
}

describe("Urdu coverage", () => {
  it("has no user-facing string without an Urdu translation", () => {
    const gaps = collectGaps();
    const report = [...gaps.entries()]
      .map(([text, where]) => `  ${where}  ${JSON.stringify(text)}`)
      .join("\n");
    expect(
      gaps.size,
      `${gaps.size} user-facing string(s) would render in English when the app ` +
        `is switched to Urdu. Add them to UR in src/lib/lang-ur.ts (or to ` +
        `ALLOWED_ENGLISH here with a reason if they are genuinely not prose):\n${report}`,
    ).toBe(0);
  });

  it("wraps every t() key in a dictionary entry", () => {
    // The subset of the sweep that matters most: a t() call is an explicit
    // promise that the string is translatable.
    const missing: string[] = [];
    const tRe = /\bt\(\s*(["'])((?:\\.|(?!\1)[^\\])*)\1\s*[),]/g;
    for (const file of walk(SRC)) {
      const rel = path.relative(SRC, file).replace(/\\/g, "/");
      if (SKIP_PREFIXES.some((p) => rel.startsWith(p))) continue;
      const src = fs.readFileSync(file, "utf8");
      let m: RegExpExecArray | null;
      tRe.lastIndex = 0;
      while ((m = tRe.exec(src))) {
        const key = m[2].replace(/\\"/g, '"').replace(/\\'/g, "'");
        if (!key || key in DICT || ALLOWED_ENGLISH.has(key)) continue;
        missing.push(`${rel}: ${JSON.stringify(key)}`);
      }
    }
    expect(missing, `t() keys with no Urdu entry:\n${missing.join("\n")}`).toEqual([]);
  });

  it("has no duplicate keys in either dictionary", () => {
    // A repeated key silently drops the earlier translation.
    for (const file of ["lib/lang-ur.ts", "lib/learn/ur.ts"]) {
      const raw = fs.readFileSync(path.join(SRC, file), "utf8");
      const body = raw.slice(raw.indexOf("= {") + 2);
      const obj = body.slice(0, body.lastIndexOf("}") + 1);
      const keys = [...obj.matchAll(/^ {2}("(?:[^"\\]|\\.)*"|[A-Za-z_$][\w$]*):/gm)].map((m) =>
        m[1].replace(/^"|"$/g, ""),
      );
      const seen = new Set<string>();
      const dup = keys.filter((k) => (seen.has(k) ? true : (seen.add(k), false)));
      expect(dup, `duplicate keys in ${file}`).toEqual([]);
    }
  });

  it("never leaves an Urdu value identical to its English key", () => {
    // A copy/paste that forgot to translate looks correct in the dictionary
    // but renders English.
    const untranslated = Object.entries(DICT)
      .filter(([k, v]) => k === v && /[A-Za-z]{3,}/.test(k) && !SAME_IN_BOTH.has(k))
      .map(([k]) => k);
    expect(
      untranslated,
      `dictionary entries that are still English:\n${untranslated.join("\n")}`,
    ).toEqual([]);
  });
});

describe("RTL safety", () => {
  it("uses logical direction utilities, not physical ones", () => {
    // In LTR a logical utility renders identically to the physical one it
    // replaces, so there is never a reason to reach for the physical form —
    // and the physical form silently mirrors wrong once dir="rtl" is on.
    const BANNED: [RegExp, string][] = [
      [/\btext-left\b/, "text-start"],
      [/\btext-right\b/, "text-end"],
      [/\bml-(auto|\d)/, "ms-*"],
      [/\bmr-(auto|\d)/, "me-*"],
      [/\bpl-\d/, "ps-*"],
      [/\bpr-\d/, "pe-*"],
      [/\bborder-l\b/, "border-s"],
      [/\bborder-r\b/, "border-e"],
      [/\brounded-l\b/, "rounded-s"],
      [/\brounded-r\b/, "rounded-e"],
    ];
    const offenders: string[] = [];
    for (const file of walk(SRC)) {
      const rel = path.relative(SRC, file).replace(/\\/g, "/");
      // Vendored shadcn primitives keep upstream classes so they stay diffable.
      if (rel.startsWith("components/ui/") || rel === "routeTree.gen.ts") continue;
      const src = fs.readFileSync(file, "utf8");
      for (const m of src.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)) {
        const cls = m[1] ?? m[2] ?? "";
        for (const [re, fix] of BANNED) {
          if (!re.test(cls)) continue;
          const ln = src.slice(0, m.index).split("\n").length;
          offenders.push(`${rel}:${ln}  ${re.source} -> use ${fix}`);
        }
      }
    }
    expect(offenders, `physical direction utilities break RTL:\n${offenders.join("\n")}`).toEqual(
      [],
    );
  });
});
