#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${TMPDIR:-}" && -d "$TMPDIR" ]]; then
  tmp_dir="$(mktemp -d "${TMPDIR%/}/staging-smoke.XXXXXX")"
else
  tmp_dir="$(mktemp -d "$repo_root/.staging-smoke.XXXXXX")"
fi
trap 'rm -rf "$tmp_dir"' EXIT
mkdir -p "$tmp_dir/bin"

cat > "$tmp_dir/bin/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
set -euo pipefail
url="${@: -1}"
if [[ "$url" == */healthz/ ]]; then
  health_body="${MOCK_HEALTH_BODY:-}"
  if [[ -z "$health_body" ]]; then
    health_body='{"status":"ok"}'
  fi
  printf '%s\n' "$health_body"
else
  printf '%s' "${MOCK_ROOT_STATUS:-200}"
fi
MOCK_CURL
chmod +x "$tmp_dir/bin/curl"

if PATH="$tmp_dir/bin:$PATH" STAGING_URL='http://staging.example.com' \
  bash "$repo_root/scripts/check_staging_smoke.sh" >/dev/null 2>&1; then
  printf 'FAIL: HTTP staging URL was accepted\n' >&2
  exit 1
fi

PATH="$tmp_dir/bin:$PATH" STAGING_URL='https://staging.example.com/' \
  bash "$repo_root/scripts/check_staging_smoke.sh" > "$tmp_dir/success.log"
grep -q 'PASS: staging home page and database readiness endpoint are healthy' "$tmp_dir/success.log"

if PATH="$tmp_dir/bin:$PATH" STAGING_URL='https://staging.example.com' \
  MOCK_ROOT_STATUS=503 bash "$repo_root/scripts/check_staging_smoke.sh" >/dev/null 2>&1; then
  printf 'FAIL: unhealthy home page was accepted\n' >&2
  exit 1
fi

if PATH="$tmp_dir/bin:$PATH" STAGING_URL='https://staging.example.com' \
  MOCK_HEALTH_BODY='{"status":"unhealthy"}' \
  bash "$repo_root/scripts/check_staging_smoke.sh" >/dev/null 2>&1; then
  printf 'FAIL: unhealthy database readiness response was accepted\n' >&2
  exit 1
fi

printf 'PASS: staging smoke checks reject HTTP, failing home, and unhealthy database responses\n'
