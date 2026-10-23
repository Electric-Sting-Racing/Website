#!/usr/bin/env bash
# Creates or updates the fsae_web role. Safe to run again: after restores, password changes, or
# if migrations were ever run as a different role.
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-$root/.env}"

# Takes a value from the exported environment, else from .env, else the default. .env is read one
# KEY=value line at a time and never sourced: values such as TEAM_LOCATION contain spaces and &.
setting() {
  local name="$1" default="$2" value
  if [[ -n "${!name:-}" ]]; then
    printf '%s' "${!name}"
    return
  fi
  value=""
  if [[ -r "$env_file" ]]; then
    value="$(grep -E "^${name}=" "$env_file" | tail -n 1 | sed -E "s/^${name}=//; s/\r$//; s/^\"(.*)\"$/\1/; s/^'(.*)'$/\1/" || true)"
  fi
  printf '%s' "${value:-$default}"
}

owner="$(setting DB_USER fsae_app)"
database="$(setting DB_NAME fsae)"
web_user="$(setting DB_WEB_USER fsae_web)"
[[ "$web_user" != "$owner" ]] || { printf 'DB_WEB_USER and DB_USER are both %s; they must be different roles\n' "$owner" >&2; exit 1; }
password_file="${DB_WEB_PASSWORD_FILE:-$root/secrets/db_web_password.txt}"
[[ -s "$password_file" ]] || { printf 'missing %s\n' "$password_file" >&2; exit 1; }
password="$(<"$password_file")"; password="${password//[$'\r\n']/}"
[[ "$password" =~ ^[A-Za-z0-9+/=]{24,}$ ]] || { printf 'generate the password with: openssl rand -hex 32\n' >&2; exit 1; }
read -ra psql_command <<<"${PSQL_COMMAND:-docker compose exec -T db psql}"
printf 'owner %s, database %s, web user %s\n' "$owner" "$database" "$web_user"
# The password goes in on stdin, never as an argument, so it never shows in the process list.
{ printf '\\set web_password %s\n\\set web_user %s\n' "$password" "$web_user"
  cat "$root/scripts/postgres/web_role.sql"; } \
  | "${psql_command[@]}" -X -q -v ON_ERROR_STOP=1 -U "$owner" -d "$database"
printf 'web role %s is ready in %s\n' "$web_user" "$database"
