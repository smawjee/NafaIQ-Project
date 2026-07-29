#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const E2E_ROOT = path.resolve(HERE, "..");

const run = spawnSync(
  "pnpm",
  ["exec", "playwright", "test", ...process.argv.slice(2)],
  {
    cwd: E2E_ROOT,
    stdio: "inherit",
  },
);

if (run.status === 0) {
  console.log("E2E is green; there is no failure to open.");
  process.exit(0);
}

console.log(
  "\nA hard failure was found. Opening the first failure in live replay mode...\n",
);
const replay = spawnSync(
  process.execPath,
  [path.join(HERE, "replay-failure.mjs"), "1"],
  {
    cwd: E2E_ROOT,
    stdio: "inherit",
  },
);

process.exit(replay.status ?? run.status ?? 1);
