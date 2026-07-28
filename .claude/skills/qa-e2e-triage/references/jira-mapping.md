# Jira mapping reference

Everything the skill needs to talk to Jira. Loaded on demand — the SKILL.md
body stays short.

## Target

| Field | Value |
|---|---|
| `cloudId` | `ac6b5877-a004-4e3e-a28c-b0b8ad275c17` |
| Site | `nafaiq.atlassian.net` |
| `projectKey` | `KAN` (Folio3-NafaIQ) |
| `issueTypeName` | `Bug` (id `10010`) |

The project is **team-managed** (`simplified: true`).

## Fields that must NOT be sent

`priority`, `components`, `environment` are **not on the KAN Bug create
screen**. Passing them in `additional_fields` fails the request with a 400.
`labels` **is** available and is what the dedupe key rides on.

## Labels

```
e2e, playwright, automated-qa, e2e-fp-<12-hex>, e2e-proj-<projectName>
```

The fingerprint lives in a **label**, not the summary:

- `labels = "x"` is an exact JQL match; `summary ~ "x"` is a fuzzy full-text
  match that tokenises hex strings unpredictably and returns false positives.
- A human renaming a ticket summary must not break dedupe.

## Dedupe query

One batched call per run, not one per failure:

```jql
project = KAN AND issuetype = Bug
  AND labels IN ("e2e-fp-a1b2c3d4e5f6", "e2e-fp-9f8e7d6c5b4a")
  AND statusCategory != Done
ORDER BY created DESC
```

Request `fields: ["summary","status","labels","created"]`, then bucket the
results by their `e2e-fp-*` label locally.

`statusCategory != Done` rather than a named status: team-managed projects
allow custom statuses, and `statusCategory` is the portable filter.

## Decision table

| Search result | Action |
|---|---|
| 0 open issues | `createJiraIssue` |
| ≥1 open issue | `addCommentToJiraIssue` on the newest. Never a second ticket, never an auto-transition. |
| `infraErrors` non-empty | ONE ticket, summary `[E2E][infra] …`, label `e2e-fp-infra-<hash>`. Skip per-test filing entirely. |
| >8 new fingerprints | Stop and ask, even with `--yes`. |

## Summary format

```
[E2E] <project> · <full title>
```

Truncate to 200 characters.

## Description template

```markdown
Automated end-to-end failure, filed by the `qa-e2e-triage` skill.

| Field | Value |
|---|---|
| Test | `<fullTitle>` |
| Spec | `<file>:<line>` |
| Playwright project | `<project>` |
| Status | `<status>` (last attempt: `<lastResultStatus>`) |
| Retries | `<retries>` |
| Duration | `<durationMs>` ms |
| Commit | `<sha>` on `<branch>` (`<author>`) |
| Run started | `<startTime>` |
| Fingerprint | `<fingerprint>` |

### Error

    <message>

### Stack

    <stack>

### Code frame

    <snippet>

### Reproduce locally

    <repro>

### Artifacts

Trace, screenshot and video are in the local run output, or in the
`playwright-report-<run_id>` GitHub Actions artifact. Open a trace with:

    pnpm --filter @nafaiq/e2e exec playwright show-trace <trace.zip>

_Do not remove the `e2e-fp-*` label — it is how this skill avoids filing a
duplicate._
```

Cap the description at 30 000 characters (the tool's limit is 32 000).

## Follow-up comment template

Used when the fingerprint already has an open issue:

```
Still failing on `<sha>` (`<branch>`).
Last attempt: `<lastResultStatus>` after <retries> retries.

    <message>
```
