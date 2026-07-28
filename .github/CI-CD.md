# CI/CD integration guide

How the test suite gates merges and deploys. Written during QA week; everything
below was verified against the repo as it stands unless explicitly marked
**unverified**.

---

## 1. What runs

`.github/workflows/ci.yml` — triggers on `push` to `main`/`dev`, on every
`pull_request`, and manually.

| Job | What it runs | Notes |
|---|---|---|
| `node-checks` | `pnpm turbo run typecheck` | Covers web, mobile, shared, e2e |
| `web-unit` | `vitest run` in `frontend/packages/web` | Needs the three `VITE_SUPABASE_*` secrets |
| `mobile-unit` | `jest --ci --runInBand` | No secrets |
| `backend-tests` | `pytest -q` | **Runs with Supabase credentials empty** — see §2 |
| `e2e` | Playwright, `public-chromium` + `authed-chromium` | `continue-on-error: true` for now — see §5 |
| `ci-required` | Aggregates all of the above | **The only check to require in branch protection** |

`.github/workflows/nightly-e2e.yml` — scheduled 03:00 UTC weekdays, matrixed
over `public-chromium`, `authed-chromium`, `authed-mobile`. Off the merge path.

### Why one aggregate check

Requiring `ci-required` instead of five individual job names means renaming or
adding a job never silently drops a protection rule. It also means a future
deploy job can `needs: [ci-required]` inside the same workflow, avoiding the
`workflow_run` double-fire you get when gating across two workflows.

### Why `lint` is not in `node-checks`

`pnpm turbo run lint` currently reports **~1,416 pre-existing errors** in the
web package, nearly all Prettier formatting. Adding it now would make CI red on
day one for reasons unrelated to any PR. Either run `eslint --fix` across the
web package and add `lint` to the `node-checks` step, or leave it out until
that cleanup lands. Mobile lint is already clean (0 errors).

---

## 2. Backend credentials: leave them EMPTY

This is the single least obvious part of the setup.

About ten backend test files carry:

```python
pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)
```

That guard checks **truthiness**, so *any* non-empty value satisfies it —
including a placeholder. Setting dummy credentials therefore makes those tests
run against a server that does not exist.

Measured, full suite, same commit:

| Configuration | Result |
|---|---|
| Credentials **empty** | **1170 passed, 0 failed, 31 skipped** |
| Credentials **dummy** | 1159 passed, **14 failed** |

The backend suite is fully green with credentials absent. (It briefly carried
one real failure, KAN-2 — the assistant tool schemas had grown past their own
7000-character budget — which is now fixed.)

A dozen tests that are logically offline still construct a `CacheLayer`, whose
`__init__` calls `get_supabase()` and raised without credentials.
`backend/tests/conftest.py` now hands back an inert client in that case, so they
run in CI while still failing loudly if they ever touch the real client.

---

## 3. Required GitHub secrets

### Setting them

**Requires ADMIN on the repository** — `push` is not enough; GitHub restricts
Actions secrets to admins. Check yours with:

```bash
gh api repos/usmankhalidj15-glitch/NafaIQ-MainProject --jq .permissions
```

All ten values already exist in the two gitignored `.env` files, so there is no
need to copy any of them by hand:

```bash
bash .github/scripts/set-secrets.sh            # dry run — shows names only
bash .github/scripts/set-secrets.sh --apply    # sets them via gh
gh secret list --repo usmankhalidj15-glitch/NafaIQ-MainProject   # verify
```

The script never prints a secret value. Anyone running it needs both `.env`
files present locally and admin on the repo.

Web UI alternative: **Settings → Secrets and variables → Actions → New
repository secret**, once per row below.


| Secret | Used by | Source |
|---|---|---|
| `VITE_SUPABASE_URL` | web-unit, e2e | `frontend/packages/web/.env` |
| `VITE_SUPABASE_ANON_KEY` | web-unit, e2e | same |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | web-unit, e2e | same |
| `VITE_PSX_API_TOKEN` | e2e | same |
| `VITE_DEMO_EMAIL` | e2e | same (`demo@nafaiq.com`) |
| **`VITE_DEMO_PASSWORD`** | e2e | **currently EMPTY in `frontend/packages/web/.env`** — see the warning below |
| `SUPABASE_URL` | e2e backend only | root `.env` |
| `SUPABASE_SECRET_KEY` | e2e backend only | root `.env` |
| `SUPABASE_JWT_SECRET` | e2e backend only | root `.env` |
| `PSX_API_TOKEN` | e2e backend only | root `.env` |

The e2e job's uvicorn **does** need real credentials — it serves live read-only
market data to the app under test. The `backend-tests` job does **not** (§2).

### ⚠ `VITE_DEMO_PASSWORD` is not set anywhere yet

`frontend/packages/web/.env` declares `VITE_DEMO_PASSWORD=` with an **empty
value**. Consequences, both verified:

- The **authed e2e project cannot run.** `tests/auth.setup.ts` fails fast with
  `VITE_DEMO_PASSWORD must be set`, and its 9 dependent specs are skipped. The
  `public-chromium` project is unaffected and green.
- The **"Try Demo" button is broken on any environment using this `.env`** —
  `src/hooks/use-demo.ts:17` throws `Demo password not configured` before it
  ever calls Supabase.

Someone with access to the `demo@nafaiq.com` credentials needs to populate it
locally **and** add it as a GitHub secret. Until then the authed journeys are
written but unverified.

**Jira credentials are deliberately absent.** The `qa-e2e-triage` skill runs in
a developer's Claude Code session against the OAuth'd MCP server. Putting a Jira
token in CI would let unattended nightly runs file tickets with no human in the
loop — exactly the risk the skill's confirmation gate exists to prevent. If
CI-side filing is ever wanted, scope it to the nightly workflow only, never PRs.

---

## 4. Blocking Vercel (web)

### Primary — branch protection (recommended)

Vercel only builds Production from the Production Branch. Protect that branch
and production is protected transitively, with no scripts and no extra token.

1. Vercel → Settings → Git → **Production Branch = `main`**.
2. Keep preview deploys on for other branches — QA reviews previews before merge.
3. GitHub → require `ci-required` on `main`, **with admin bypass disabled** (§6).

### Defense in depth — Ignored Build Step

Covers the force-push / admin path that branch protection alone does not.

Vercel → Settings → Git → **Ignored Build Step** → *Custom*:

```
bash frontend/packages/web/scripts/vercel-ignore-build.sh
```

The semantics are inverted and routinely gotten wrong:
**exit 1 = skip the build, exit 0 = build.**

```bash
#!/usr/bin/env bash
# exit 1 => SKIP build. exit 0 => BUILD.
# Needs GH_STATUS_TOKEN (fine-grained PAT: Checks:read + Contents:read) as a
# Vercel Environment Variable on the Production environment.
set -uo pipefail

REPO="usmankhalidj15-glitch/NafaIQ-MainProject"
SHA="${VERCEL_GIT_COMMIT_SHA:-}"

# Previews should build while CI runs — that is how QA reviews a PR.
[ "${VERCEL_ENV:-}" != "production" ] && exit 0
[ -z "$SHA" ] && { echo "no SHA; skipping"; exit 1; }
[ -z "${GH_STATUS_TOKEN:-}" ] && { echo "GH_STATUS_TOKEN unset; skipping"; exit 1; }

# Vercel starts building the instant the push lands, so CI is normally still
# pending. Poll rather than skip. jq is not guaranteed in the build image; node is.
for i in $(seq 1 40); do   # 40 * 15s = 10 minutes
  BODY=$(curl -sS -H "Authorization: Bearer $GH_STATUS_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/commits/$SHA/check-runs?per_page=100")

  STATE=$(node -e '
    let s=""; process.stdin.on("data",d=>s+=d).on("end",()=>{
      const runs=(JSON.parse(s).check_runs||[]).filter(r=>r.name==="ci-required");
      if(!runs.length) return console.log("missing");
      const r=runs[0];
      console.log(r.status!=="completed" ? "pending" : r.conclusion);
    });' <<<"$BODY")

  case "$STATE" in
    success) echo "ci-required passed -> building"; exit 0 ;;
    pending|missing) echo "ci-required $STATE ($i/40)"; sleep 15 ;;
    *) echo "ci-required = $STATE -> skipping build"; exit 1 ;;
  esac
done
echo "ci-required never completed -> skipping build"; exit 1
```

Trade-off to state plainly: Vercel caps how long the ignore step may run, so a
CI run slower than ~10 minutes gets skipped. That fails safe (no deploy) but
needs a manual redeploy.

### Deploy-from-Action (optional, maximum control)

Disable Vercel's Git trigger, add to `frontend/packages/web/vercel.json`:

```json
{ "git": { "deploymentEnabled": { "main": false } } }
```

then append a `deploy-web` job with `needs: [ci-required]` using
`vercel pull/build/deploy --prebuilt --prod`.

**Unverified and worth checking first:** `@lovable.dev/vite-tanstack-config`
defaults the nitro preset to `cloudflare-module`, and
`frontend/packages/web/.wrangler/deploy` exists in the repo. `vercel build` may
need an explicit `nitro: { preset: "vercel" }` — a real change to the app's
build. Confirm which platform actually serves production before adopting this.

---

## 5. Blocking Railway (backend)

Railway builds `backend/Dockerfile` from `main` (`railway.json`).

### Primary — "Wait for CI"

Railway Dashboard → backend service → **Settings → Deploys** (under the GitHub
source config) → enable **Wait for CI**. Also set the deployment trigger branch
to `main` only, so `dev` pushes never deploy.

Two caveats that matter:

1. **If a commit has no check runs at all, Railway has nothing to wait for and
   deploys.** This is why `ci.yml` must trigger on `push: branches: [main]`, not
   only `pull_request` — otherwise the gate silently no-ops on merge commits.
2. Wait for CI waits for the **whole** suite, e2e included. That makes the
   anti-flake work in the e2e config load-bearing for deploys, not just for PRs.
   This is why `e2e` currently carries `continue-on-error: true`: land it,
   watch the flake rate for a week, then remove that line to make it a hard gate.

### Alternative — deploy from the Action

Disconnect Railway's auto-deploy, then add a `deploy-backend` job with
`needs: [ci-required]` running `railway up --service "$RAILWAY_SERVICE" --detach`
with a **project** token (Project Settings → Tokens) in `RAILWAY_TOKEN`.

Prefer Wait for CI: it keeps Railway's build cache and rollback UX, and is one
fewer long-lived credential in GitHub.

---

## 6. Branch protection

### `main`

- Require a pull request before merging — 1 approval, dismiss stale approvals
- Require status checks → **`ci-required`** (that one check only)
- Require branches to be up to date before merging: **ON** — otherwise a green
  PR can merge onto a stale base, break `main`, and be deployed
- Require conversation resolution: ON
- Block force pushes: ON · Restrict deletions: ON
- **Do not allow bypassing the above: ON** — with admin bypass enabled all of
  this is advisory, and the Vercel ignore-step script becomes the only real guard

```bash
gh api -X PUT repos/usmankhalidj15-glitch/NafaIQ-MainProject/branches/main/protection \
  -H "Accept: application/vnd.github+json" --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["ci-required"] },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
```

### `dev`

Same body with `"required_pull_request_reviews": null` and
`"enforce_admins": false` — gated on CI, but 0 approvals so integration velocity
is preserved.

### Personal branches (`tayyib`, `usman`, …)

No ruleset. The bare `pull_request:` trigger still runs the full suite on any PR
regardless of target, so authors get signal before opening against `dev`.

---

## 7. Rollout order

1. ~~Fix KAN-2~~ — done; `backend-tests` is green (1170 passed).
2. Add the secrets in §3.
3. Merge the workflows. Watch a few runs; `e2e` is non-blocking at this stage.
4. Decide on the lint cleanup (§1) and add `lint` to `node-checks`.
5. Enable branch protection on `main`, then `dev`.
6. Remove `continue-on-error: true` from the `e2e` job once its flake rate is known.
7. Enable Railway **Wait for CI** last, after CI has been green across several
   consecutive `main` pushes.

Note that the `e2e` job still carries one known failure: the landing spec
catches the KAN-4 router-preload errors. That is why `e2e` is
`continue-on-error` at step 3 — fix KAN-4 before step 6.
