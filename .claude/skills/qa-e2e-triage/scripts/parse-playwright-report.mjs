#!/usr/bin/env node
// Normalise a Playwright JSON report into a flat, Jira-ready failure list.
//
// Usage: node parse-playwright-report.mjs [path/to/results.json]
// Prints JSON to stdout. ALWAYS exits 0 — the caller decides what a red suite
// means, so a non-zero exit here would just look like the script itself broke.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { execSync } from "node:child_process";

const REPORT = process.argv[2] ?? "frontend/packages/e2e/reports/results.json";

if (!existsSync(REPORT)) {
  console.log(JSON.stringify({ ok: false, reason: "report-missing", path: REPORT }, null, 2));
  process.exit(0);
}

const report = JSON.parse(readFileSync(REPORT, "utf8"));

// Playwright colourises error messages; unstripped they render as [2m[31m
// garbage in a Jira description.
const ANSI = /\[[0-9;]*[A-Za-z]/g;
const clean = (s, maxLines) =>
  String(s ?? "")
    .replace(ANSI, "")
    .split("\n")
    .slice(0, maxLines)
    .join("\n")
    .trim();

/**
 * Stable across runs; changes only when the spec is renamed or moved — which is
 * exactly when a NEW ticket is wanted. Independent of Playwright internals.
 */
const fingerprint = (file, title, project) =>
  createHash("sha1").update(`${file}::${title}::${project}`).digest("hex").slice(0, 12);

const git = (cmd, fallback = "unknown") => {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return fallback;
  }
};

const failures = [];
const flaky = [];

function walk(suite, ancestry, depth) {
  // At depth 0 the suite title IS the file path — already captured as spec.file.
  const titles = depth === 0 ? ancestry : [...ancestry, suite.title].filter(Boolean);

  for (const spec of suite.specs ?? []) {
    for (const t of spec.tests ?? []) {
      // Filter on TEST status, not result status: "flaky" means it passed on a
      // retry, and retries are 2 on CI by design.
      if (t.status === "expected" || t.status === "skipped") continue;

      const results = t.results ?? [];
      const last = results[results.length - 1] ?? {};
      const err = last.error ?? (last.errors ?? [])[0] ?? {};
      const titlePath = [...titles, spec.title].filter(Boolean);
      const fullTitle = titlePath.join(" › ");

      const rec = {
        title: spec.title,
        titlePath,
        fullTitle,
        file: spec.file,
        line: spec.line,
        column: spec.column,
        project: t.projectName,
        status: t.status, // "unexpected" | "flaky"
        lastResultStatus: last.status, // "failed" | "timedOut" | ...
        retries: Math.max(0, results.length - 1),
        durationMs: results.reduce((a, r) => a + (r.duration ?? 0), 0),
        startTime: results[0]?.startTime ?? null,
        message: clean(err.message, 40) || "(no error message)",
        stack: clean(err.stack, 60),
        snippet: clean(err.snippet, 25),
        errorLocation: err.location ?? null,
        attachments: (last.attachments ?? []).map((a) => ({ name: a.name, path: a.path })),
        repro:
          `pnpm --filter @nafaiq/e2e exec playwright test "${spec.file}" ` +
          `-g ${JSON.stringify(spec.title)} --project=${t.projectName}`,
        fingerprint: fingerprint(spec.file, fullTitle, t.projectName),
      };

      (t.status === "flaky" ? flaky : failures).push(rec);
    }
  }

  for (const child of suite.suites ?? []) walk(child, titles, depth + 1);
}

for (const s of report.suites ?? []) walk(s, [], 0);

// A non-empty top-level `errors` array means the CONFIG or a webServer failed —
// one infrastructure bug, not N test bugs. Filing 22 tickets because uvicorn
// did not boot is the exact failure mode this separation prevents.
const infraErrors = (report.errors ?? []).map((e) => ({
  message: clean(e.message, 40),
  stack: clean(e.stack, 30),
}));

console.log(
  JSON.stringify(
    {
      ok: failures.length === 0 && infraErrors.length === 0,
      stats: report.stats ?? null,
      rootDir: report.config?.rootDir ?? null,
      infraErrors,
      git: {
        sha: git("git rev-parse --short HEAD"),
        branch: git("git rev-parse --abbrev-ref HEAD"),
        author: git("git log -1 --pretty=%an"),
      },
      counts: { failed: failures.length, flaky: flaky.length },
      failures,
      flaky,
    },
    null,
    2,
  ),
);
