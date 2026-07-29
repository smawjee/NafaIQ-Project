#!/usr/bin/env bash
# Run the Playwright suite and ALWAYS exit 0.
#
# A red suite is this skill's INPUT, not an error condition — exiting non-zero
# here would make a legitimately-failing run look like the tooling broke.
# The JSON report at the stable path is the contract.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 0

# The demo credentials live in the web package's .env; the authed project cannot
# sign in without them (src/hooks/use-demo.ts throws on a blank password).
if [ -f frontend/packages/web/.env ]; then
  set -a
  # shellcheck disable=SC1091
  . frontend/packages/web/.env
  set +a
fi

pnpm --filter @nafaiq/e2e exec playwright test "$@" 2>&1 | tail -n 80

echo "---"
echo "report: frontend/packages/e2e/reports/results.json"
echo "html:   frontend/packages/e2e/reports/html/index.html"
exit 0
