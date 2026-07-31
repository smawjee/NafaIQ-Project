#!/usr/bin/env node

import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const E2E_ROOT = path.resolve(HERE, "..");
const REPORT = path.join(E2E_ROOT, "reports/results.json");

function fingerprint(file, title, project) {
  return createHash("sha1")
    .update(`${file}::${title}::${project}`)
    .digest("hex")
    .slice(0, 12);
}

function collectFailures(report) {
  const failures = [];

  function walk(suite, ancestry = [], depth = 0) {
    const titles =
      depth === 0 ? ancestry : [...ancestry, suite.title].filter(Boolean);
    for (const spec of suite.specs ?? []) {
      for (const test of spec.tests ?? []) {
        if (test.status !== "unexpected") continue;
        const fullTitle = [...titles, spec.title].filter(Boolean).join(" › ");
        failures.push({
          file: spec.file,
          line: spec.line,
          title: spec.title,
          fullTitle,
          project: test.projectName,
          fingerprint: fingerprint(spec.file, fullTitle, test.projectName),
        });
      }
    }
    for (const child of suite.suites ?? []) walk(child, titles, depth + 1);
  }

  for (const suite of report.suites ?? []) walk(suite);
  return failures;
}

function printFailures(failures) {
  for (const [index, failure] of failures.entries()) {
    console.log(
      `${index + 1}. [${failure.project}] ${failure.fullTitle} ` +
        `(${failure.file}:${failure.line}, fp ${failure.fingerprint})`,
    );
  }
}

if (!existsSync(REPORT)) {
  console.error(`No Playwright JSON report found at ${REPORT}`);
  console.error("Run pnpm test:e2e first.");
  process.exit(1);
}

const args = process.argv.slice(2);
const listOnly = args.includes("--list");
const dryRun = args.includes("--dry-run");
const selector = args.find((arg) => !arg.startsWith("--")) ?? "1";
const report = JSON.parse(readFileSync(REPORT, "utf8"));
const failures = collectFailures(report);

if (failures.length === 0) {
  console.log("The latest Playwright report has no hard failures to replay.");
  process.exit(0);
}

if (listOnly) {
  printFailures(failures);
  process.exit(0);
}

const numericIndex = Number(selector);
const selected = Number.isInteger(numericIndex)
  ? failures[numericIndex - 1]
  : failures.find((failure) => failure.fingerprint === selector);

if (!selected) {
  console.error(`Unknown failure selector: ${selector}`);
  printFailures(failures);
  process.exit(1);
}

const playwrightArgs = [
  "exec",
  "playwright",
  "test",
  selected.file,
  "-g",
  selected.title,
  `--project=${selected.project}`,
  "--headed",
  "--workers=1",
];

console.log(`Replaying [${selected.project}] ${selected.fullTitle}`);
console.log(
  "The demo credentials will be filled through the visible sign-in form.",
);
console.log(
  "If the failure reproduces, the browser and Inspector pause at the failure state.",
);

if (dryRun) {
  console.log(
    `pnpm ${playwrightArgs.map((arg) => JSON.stringify(arg)).join(" ")}`,
  );
  process.exit(0);
}

const result = spawnSync("pnpm", playwrightArgs, {
  cwd: E2E_ROOT,
  env: {
    ...process.env,
    E2E_LIVE_REPLAY: "1",
    E2E_VISIBLE_LOGIN: "1",
    E2E_PAUSE_ON_FAILURE: "1",
    E2E_REPLAY_SUCCESS_DELAY_MS:
      process.env.E2E_REPLAY_SUCCESS_DELAY_MS ?? "5000",
  },
  stdio: "inherit",
});

process.exit(result.status ?? 1);
