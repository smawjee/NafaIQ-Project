# NafaIQ Postman QA

This directory contains two Postman collections:

- `NafaIQ API.postman_collection.json` — the ordered end-to-end QA suite.
- `NafaIQ API Catalog.postman_collection.json` — every operation currently
  published by FastAPI's OpenAPI schema.

The E2E suite is the collection to run in Friday's presentation. The catalog is
for coverage, discovery, and manually inspecting individual APIs. Do not run
the complete catalog unattended: it includes admin, bulk-delete, import, AI,
and OAuth operations.

## Import into Postman

1. Import `NafaIQ API.postman_collection.json`.
2. Import either environment from `postman/environments/`.
3. Duplicate the imported environment before adding secrets.
4. Fill in:
   - `base_url`
   - `supabase_url`
   - `supabase_anon_key`
   - `demo_email` and `demo_password`
5. Select the environment and run the collection.

Instead of a demo email and password, a short-lived `user_jwt` can be supplied
directly. The sign-in request is skipped when a JWT exists and the two demo
credential fields are blank.

The committed environments are templates. Never commit populated credentials,
JWTs, the shared PSX token, or the backend-only admin token.

## Command-line execution

Install workspace dependencies once:

```bash
pnpm install
```

Run the public, read-only checks:

```bash
pnpm test:api:public
```

Run the complete stable E2E journey with credentials supplied at runtime:

```bash
NAFAIQ_SUPABASE_URL="https://project.supabase.co" \
NAFAIQ_SUPABASE_ANON_KEY="..." \
NAFAIQ_DEMO_EMAIL="qa@example.com" \
NAFAIQ_DEMO_PASSWORD="..." \
pnpm test:api
```

To test Dev rather than Local:

```bash
POSTMAN_ENVIRONMENT="postman/environments/NafaIQ Dev.postman_environment.json" \
NAFAIQ_SUPABASE_URL="https://project.supabase.co" \
NAFAIQ_SUPABASE_ANON_KEY="..." \
NAFAIQ_DEMO_EMAIL="qa@example.com" \
NAFAIQ_DEMO_PASSWORD="..." \
pnpm test:api
```

The CLI creates `postman/reports/junit.xml`, which can be uploaded as a CI test
artifact. The reports directory is ignored by Git.

## What the E2E collection validates

The runner performs these journeys in order:

1. Check API readiness and obtain a Supabase user JWT.
2. Verify public platform, market, macro, news, funds, and LearnHub APIs.
3. Reuse a dedicated `Postman QA` portfolio—or a safe existing portfolio when
   the account is at its portfolio limit—exercise holding CRUD, and clean up
   the holding without touching pre-existing positions.
4. Add and remove a watchlist symbol while preserving a pre-existing entry.
5. Exercise transaction CRUD and read finance summaries.
6. Create, update, and clean up a goal, budget, and bill.
7. Create, toggle, and clean up application and price alerts.
8. Verify notification reads.
9. Confirm missing authentication and invalid request bodies are rejected.

AI and email-integration reads are in the optional folder and skipped by
default. Set the collection variable `run_optional_requests` to `true` when the
required providers and OAuth integration are intentionally available.

### Cleanup limitation

The backend does not expose a portfolio-delete operation. The collection
therefore reuses one empty portfolio named `Postman QA` between runs. If the
account is already at its portfolio limit, it selects an existing portfolio,
chooses a stock that is not already held there, and removes only the holding it
created. All holdings and other records created during a successful run are
deleted. If a run stops in the middle of the dedicated-portfolio journey, the
next run removes a stale QA holding before continuing.

Goal, budget, bill, and price-alert creation can still fail when the selected
demo account is already at its plan limit. Use a dedicated QA user with room
under those limits for deterministic presentation runs.

## Refresh after API changes

FastAPI is the source of truth. Refresh the OpenAPI snapshot and both
collections with:

```bash
backend/.venv/bin/python postman/generate_collection.py --refresh-openapi
```

Once `postman/openapi.json` is current, collection-only regeneration needs no
backend dependencies:

```bash
python3 postman/generate_collection.py
```

The generator mirrors authentication routing from
`backend/src/app/middleware/auth.py`. If those rules change, update the
generator's route classification at the same time.
