#!/usr/bin/env bash
set -euo pipefail

: "${STAGING_URL:?Set STAGING_URL to the public HTTPS staging base URL}"

python3 - "$STAGING_URL" <<'PY'
import sys
from urllib.parse import urlsplit

try:
    parsed = urlsplit(sys.argv[1])
    port = parsed.port
except ValueError as exc:
    raise SystemExit(f"Invalid STAGING_URL: {exc}")

if parsed.scheme != "https" or not parsed.hostname:
    raise SystemExit("STAGING_URL must be an absolute HTTPS URL")
if parsed.username is not None or parsed.password is not None:
    raise SystemExit("STAGING_URL must not contain credentials")
if parsed.query or parsed.fragment:
    raise SystemExit("STAGING_URL must not contain a query string or fragment")
PY

base_url="${STAGING_URL%/}"
root_status="$(curl --fail --silent --show-error --location \
  --proto '=https' --proto-redir '=https' --max-time 30 \
  --output /dev/null --write-out '%{http_code}' "$base_url/")"
if [[ "$root_status" != "200" ]]; then
  printf 'FAIL: staging home page returned HTTP %s\n' "$root_status" >&2
  exit 1
fi

health_body="$(curl --fail --silent --show-error --location \
  --proto '=https' --proto-redir '=https' --max-time 30 \
  --header 'Accept: application/json' "$base_url/healthz/")"
python3 - "$health_body" <<'PY'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except json.JSONDecodeError as exc:
    raise SystemExit(f"FAIL: /healthz/ returned invalid JSON: {exc}")

if payload != {"status": "ok"}:
    raise SystemExit(f"FAIL: /healthz/ returned unexpected status: {payload!r}")
PY

printf 'PASS: staging home page and database readiness endpoint are healthy\n'
