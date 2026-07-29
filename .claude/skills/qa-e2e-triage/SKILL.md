---
name: qa-e2e-triage
description: Run the NafaIQ Playwright end-to-end suite, parse the JSON reporter output at frontend/packages/e2e/reports/results.json, and file or update Jira Bugs in project KAN for every failing test, with fingerprint-based duplicate suppression. Use when asked to run e2e tests, run Playwright, triage e2e or QA failures, file bugs from test failures, check the suite before a release, or "why is e2e red".
argument-hint: "[--suite public|authed|all] [--project <name>] [--report <path>] [--dry-run] [--yes]"
allowed-tools: Bash, Read, Glob, Grep, mcp__jira__searchJiraIssuesUsingJql, mcp__jira__createJiraIssue, mcp__jira__addCommentToJiraIssue, mcp__jira__getJiraProjectIssueTypesMetadata
metadata:
  author: nafaiq-qa
  version: "1.0.0"
---

# QA E2E Triage

Runs Playwright, turns red tests into Jira Bugs, and never files the same bug
twice.

## Workflow

1. **Run.**
   ```bash
   bash .claude/skills/qa-e2e-triage/scripts/run-e2e.sh [playwright args]
   ```
   Always exits 0. Loads the demo credentials from `frontend/packages/web/.env`
   — the authed project cannot sign in without `VITE_DEMO_PASSWORD`.
   Map `--suite`: `public` → `--project=public-chromium`, `authed` →
   `--project=authed-chromium`, `all` → no project flag.

   Skip this step entirely if the user passed `--report <path>`, or asks to
   triage a run that already happened.

2. **Parse.**
   ```bash
   node .claude/skills/qa-e2e-triage/scripts/parse-playwright-report.mjs [path]
   ```
   Returns `{ok, stats, infraErrors, git, counts, failures[], flaky[]}`.
   If it returns `{ok:false, reason:"report-missing"}`, the run never produced a
   report — say so and stop; do not file anything.

3. **Branch on `infraErrors`.** Non-empty means the config or a `webServer`
   failed, not that N tests are broken. File ONE `[E2E][infra]` bug and stop.
   Filing 22 tickets because uvicorn did not boot is the exact failure this
   prevents.

4. **Circuit-breaker.** More than 8 new fingerprints in one run ⇒ stop and ask
   the user, **even with `--yes`**. That many simultaneous failures is an
   environment or shared-selector regression, not 9 separate bugs.

5. **Dedupe.** One batched JQL over all fingerprints at once — see
   `references/jira-mapping.md` for the exact query.

6. **Confirm.** Print the triage table, then ask ONCE for the whole batch.
   Skip only with `--yes`. With `--dry-run`, print the exact `createJiraIssue`
   payloads and call nothing.

7. **Write.** Create Bugs for new fingerprints; comment on existing open ones.

8. **Report.** Print created keys, commented keys, and the HTML report path.

## Triage table format

```
3 failing, 1 flaky, 18 passing — commit a1b2c3d on dev

  NEW      authed-chromium · portfolio › adds and removes a holding      fp a1b2c3d4e5f6
  NEW      authed-chromium · finance › transaction lifecycle             fp 9f8e7d6c5b4a
  KNOWN    public-chromium · psx › terminal loads   -> KAN-142 (In Progress)
  FLAKY    authed-chromium · navigation sweep       (passed on retry 1 — not filed)

Create 2 new KAN Bugs and comment on KAN-142?
```

## Rules

- **`flaky` tests are NEVER filed.** Retries are 2 on CI by design; a test that
  passed on retry is not a bug report.
- **Confirmation is ON by default.** KAN is a shared board with real people and
  ticket creation is effectively irreversible. Failures here are *correlated* —
  one expired `VITE_DEMO_PASSWORD` red-lines all five authed journeys at once —
  and dedupe only protects the *second* run.
- **Never send `priority`, `components` or `environment`**: they are not on the
  KAN Bug create screen and the request will 400.
- **Never auto-transition or auto-close** an issue.
- **Never strip the `e2e-fp-*` label** — it is the dedupe key.
- On green: **zero Jira writes**, summary only.

## Green output

```
E2E green — 22 passed, 0 failed, 0 flaky, 1m 01s (commit a1b2c3d on dev)

  public-chromium   5 passed
  authed-chromium  17 passed

HTML report: frontend/packages/e2e/reports/html/index.html
```

Optionally then offer (never perform automatically) to comment "no longer
reproducing as of `<sha>`" on any open auto-filed bug whose fingerprint is
absent from this run. Closing a bug stays a human decision.

See `references/jira-mapping.md` for the cloudId, field constraints, JQL and
description templates.
