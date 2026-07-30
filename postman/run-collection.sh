#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
collection="$repo_root/postman/NafaIQ API.postman_collection.json"
environment="${POSTMAN_ENVIRONMENT:-$repo_root/postman/environments/NafaIQ Local.postman_environment.json}"
scope="${1:-full}"
report_dir="$repo_root/postman/reports"

mkdir -p "$report_dir"

args=(
  run "$collection"
  --environment "$environment"
  --bail
  --reporters cli,junit
  --reporter-junit-export "$report_dir/junit.xml"
)

if [[ "$scope" == "public" ]]; then
  args+=(--folder "01 - Platform and Public Market")
elif [[ "$scope" != "full" ]]; then
  echo "Usage: $0 [full|public]" >&2
  exit 2
fi

# Runtime overrides keep credentials out of committed Postman files.
[[ -n "${NAFAIQ_BASE_URL:-}" ]] && args+=(--env-var "base_url=$NAFAIQ_BASE_URL")
[[ -n "${NAFAIQ_SUPABASE_URL:-}" ]] && args+=(--env-var "supabase_url=$NAFAIQ_SUPABASE_URL")
[[ -n "${NAFAIQ_SUPABASE_ANON_KEY:-}" ]] && args+=(--env-var "supabase_anon_key=$NAFAIQ_SUPABASE_ANON_KEY")
[[ -n "${NAFAIQ_DEMO_EMAIL:-}" ]] && args+=(--env-var "demo_email=$NAFAIQ_DEMO_EMAIL")
[[ -n "${NAFAIQ_DEMO_PASSWORD:-}" ]] && args+=(--env-var "demo_password=$NAFAIQ_DEMO_PASSWORD")
[[ -n "${NAFAIQ_USER_JWT:-}" ]] && args+=(--env-var "user_jwt=$NAFAIQ_USER_JWT")
[[ -n "${NAFAIQ_PSX_API_TOKEN:-}" ]] && args+=(--env-var "psx_api_token=$NAFAIQ_PSX_API_TOKEN")

cd "$repo_root"
pnpm exec newman "${args[@]}"
