#!/usr/bin/env bash
# Populate the GitHub Actions secrets that .github/workflows/ci.yml needs.
#
# Values are read from the two gitignored .env files that already exist locally,
# so nothing has to be copied by hand or pasted into a chat/ticket. Secret
# VALUES are never printed — only names and whether each was found.
#
# Requires ADMIN on the repository. `push` is not enough: GitHub restricts
# Actions secrets to admins. Check with:
#   gh api repos/<owner>/<repo> --jq .permissions
#
# Usage:
#   bash .github/scripts/set-secrets.sh            # show what would be set
#   bash .github/scripts/set-secrets.sh --apply    # actually set them
#   bash .github/scripts/set-secrets.sh --print    # print name/value pairs for
#                                                  # pasting into the web UI
#
# --print writes real secret values to your terminal. Use it only when adding
# them through Settings -> Secrets and variables -> Actions by hand, and clear
# your scrollback afterwards.
set -uo pipefail

REPO="${REPO:-usmankhalidj15-glitch/NafaIQ-MainProject}"
APPLY=0
PRINT=0
case "${1:-}" in
  --apply) APPLY=1 ;;
  --print) PRINT=1 ;;
esac

cd "$(git rev-parse --show-toplevel)" || exit 1

ROOT_ENV=".env"
WEB_ENV="frontend/packages/web/.env"

# secret name : source file
# Frontend values are public-by-design (they ship in the browser bundle); the
# backend ones are not.
declare -A SOURCES=(
  [VITE_SUPABASE_URL]="$WEB_ENV"
  [VITE_SUPABASE_ANON_KEY]="$WEB_ENV"
  [VITE_SUPABASE_PUBLISHABLE_KEY]="$WEB_ENV"
  [VITE_PSX_API_TOKEN]="$WEB_ENV"
  [VITE_DEMO_EMAIL]="$WEB_ENV"
  [VITE_DEMO_PASSWORD]="$WEB_ENV"
  [SUPABASE_URL]="$ROOT_ENV"
  [SUPABASE_SECRET_KEY]="$ROOT_ENV"
  [SUPABASE_JWT_SECRET]="$ROOT_ENV"
  # Needed by the e2e job only: main.py's lifespan reflects the schema at
  # startup, so uvicorn will not boot without these.
  [SUPABASE_DATABASE_PASSWORD]="$ROOT_ENV"
  [SUPABASE_POOLER_HOST]="$ROOT_ENV"
  [SUPABASE_POOLER_USER]="$ROOT_ENV"
  [PSX_API_TOKEN]="$ROOT_ENV"
)

# Read KEY=value from a .env without sourcing it (avoids executing anything).
read_env() {
  local key="$1" file="$2"
  [ -f "$file" ] || return 1
  local line
  line=$(grep -m1 "^${key}=" "$file") || return 1
  local value="${line#*=}"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  [ -n "$value" ] || return 1
  printf '%s' "$value"
}

if [ "$PRINT" -eq 1 ]; then
  echo "Paste each of these into Settings -> Secrets and variables -> Actions."
  echo "These are REAL VALUES — clear your scrollback when you are done."
  echo
  for name in "${!SOURCES[@]}"; do
    if value=$(read_env "$name" "${SOURCES[$name]}"); then
      printf '%s\n%s\n\n' "$name" "$value"
    else
      printf '%s\n<MISSING from %s>\n\n' "$name" "${SOURCES[$name]}"
    fi
  done
  exit 0
fi

echo "Repository: $REPO"
if [ "$APPLY" -eq 0 ]; then
  echo "Mode:       DRY RUN (pass --apply to set them)"
else
  echo "Mode:       APPLY"
fi
echo

missing=0
for name in "${!SOURCES[@]}"; do
  file="${SOURCES[$name]}"
  if value=$(read_env "$name" "$file"); then
    if [ "$APPLY" -eq 1 ]; then
      if printf '%s' "$value" | gh secret set "$name" --repo "$REPO" --body - 2>/dev/null; then
        printf '  set      %-32s (from %s)\n' "$name" "$file"
      else
        printf '  FAILED   %-32s — do you have admin on %s?\n' "$name" "$REPO"
        missing=$((missing + 1))
      fi
    else
      printf '  ready    %-32s (from %s)\n' "$name" "$file"
    fi
  else
    printf '  MISSING  %-32s — not set in %s\n' "$name" "$file"
    missing=$((missing + 1))
  fi
done

echo
if [ "$missing" -gt 0 ]; then
  echo "$missing secret(s) could not be resolved. Fix those before relying on CI."
  exit 1
fi

if [ "$APPLY" -eq 0 ]; then
  echo "All values found. Re-run with --apply to set them."
else
  echo "Done. Verify with: gh secret list --repo $REPO"
fi
