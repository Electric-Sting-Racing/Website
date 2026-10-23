#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_PARENT="${TMPDIR:-/tmp}"
if [[ ! -d "$TEMP_PARENT" ]]; then
  TEMP_PARENT="$ROOT"
fi
TEMP_DIR="$(mktemp -d "$TEMP_PARENT/.apply-roles.XXXXXX")"
trap 'rm -rf "$TEMP_DIR"' EXIT

mkdir -p "$TEMP_DIR/bin"
PASSWORD="abcdef0123456789abcdef0123456789abcdef0123456789"

# The stub records its arguments and everything it reads on stdin.
cat > "$TEMP_DIR/bin/psql" <<'PSQL'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$@" > "${STUB_ARGS:?}"
cat > "${STUB_STDIN:?}"
PSQL
chmod +x "$TEMP_DIR/bin/psql"

# run_apply <password file> <env file> [VAR=value ...]; output goes to $TEMP_DIR/output.txt.
run_apply() {
  local password_file="$1" env_file="$2"
  shift 2
  rm -f "$TEMP_DIR/args" "$TEMP_DIR/stdin"
  env -u DB_USER -u DB_NAME -u DB_WEB_USER \
    PATH="$TEMP_DIR/bin:$PATH" \
    PSQL_COMMAND="psql" \
    DB_WEB_PASSWORD_FILE="$password_file" \
    ENV_FILE="$env_file" \
    STUB_ARGS="$TEMP_DIR/args" \
    STUB_STDIN="$TEMP_DIR/stdin" \
    "$@" \
    bash "$ROOT/scripts/apply_postgres_roles.sh" >"$TEMP_DIR/output.txt" 2>&1
}

fail() {
  cat "$TEMP_DIR/output.txt" >&2 2>/dev/null || true
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

expect_refusal() {
  if run_apply "$1" "$TEMP_DIR/no.env"; then
    fail "$2"
  fi
  [[ ! -e "$TEMP_DIR/args" ]] || fail "psql ran although $2"
}

# Missing, empty and malformed password files are refused before psql runs.
expect_refusal "$TEMP_DIR/missing.txt" "a missing password file was accepted"
: > "$TEMP_DIR/empty.txt"
expect_refusal "$TEMP_DIR/empty.txt" "an empty password file was accepted"
printf 'short' > "$TEMP_DIR/short.txt"
expect_refusal "$TEMP_DIR/short.txt" "a short password was accepted"
printf '%s' "abc def'; drop table x; --0123456789abcdef" > "$TEMP_DIR/bad.txt"
expect_refusal "$TEMP_DIR/bad.txt" "a password with unsafe characters was accepted"

printf '%s\n' "$PASSWORD" > "$TEMP_DIR/password.txt"

# The password reaches psql on stdin and never in its arguments.
run_apply "$TEMP_DIR/password.txt" "$TEMP_DIR/no.env" || fail "a valid password was refused"
grep -q "$PASSWORD" "$TEMP_DIR/stdin" || fail "password missing from stdin"
if grep -q "$PASSWORD" "$TEMP_DIR/args"; then fail "password appeared in argv"; fi
if grep -q "$PASSWORD" "$TEMP_DIR/output.txt"; then fail "password was printed"; fi
grep -q 'CREATE ROLE' "$TEMP_DIR/stdin" || fail "web_role.sql was not sent"

# Defaults when nothing is exported and there is no .env.
args="$(tr '\n' ' ' < "$TEMP_DIR/args")"
[[ "$args" == *"-U fsae_app -d fsae "* ]] || fail "default owner and database not passed: $args"
grep -q '^\\set web_user fsae_web$' "$TEMP_DIR/stdin" || fail "default web user not set"
grep -q 'owner fsae_app, database fsae, web user fsae_web' "$TEMP_DIR/output.txt" || fail "resolved settings not printed"

# .env is used when nothing is exported, and odd lines in it do not break parsing.
cat > "$TEMP_DIR/team.env" <<'ENV'
DJANGO_ALLOWED_HOSTS=electricsting.example.edu
TEAM_LOCATION=Sacramento State / Engineering & Computer Science
TEAM_SEASON=2026 — 2027
# DB_USER=commented
DB_NAME="from_env_db"
DB_USER=env_owner
DB_WEB_USER='env_web'
ENV
printf 'SENTRY_DSN=\r\n' >> "$TEMP_DIR/team.env"
run_apply "$TEMP_DIR/password.txt" "$TEMP_DIR/team.env" || fail "a .env with spaces and & broke parsing"
args="$(tr '\n' ' ' < "$TEMP_DIR/args")"
[[ "$args" == *"-U env_owner -d from_env_db "* ]] || fail ".env values not used: $args"
grep -q '^\\set web_user env_web$' "$TEMP_DIR/stdin" || fail "DB_WEB_USER from .env not used"

# Carriage returns in .env are stripped.
printf 'DB_USER=crlf_owner\r\nDB_NAME=crlf_db\r\n' > "$TEMP_DIR/crlf.env"
run_apply "$TEMP_DIR/password.txt" "$TEMP_DIR/crlf.env" || fail "a CRLF .env was refused"
args="$(tr '\n' ' ' < "$TEMP_DIR/args")"
[[ "$args" == *"-U crlf_owner -d crlf_db "* ]] || fail "CRLF .env values not cleaned: $args"

# Exported variables win over .env.
run_apply "$TEMP_DIR/password.txt" "$TEMP_DIR/team.env" DB_USER=exported_owner DB_NAME=exported_db DB_WEB_USER=exported_web \
  || fail "exported settings were refused"
args="$(tr '\n' ' ' < "$TEMP_DIR/args")"
[[ "$args" == *"-U exported_owner -d exported_db "* ]] || fail "exported values did not win over .env: $args"
grep -q '^\\set web_user exported_web$' "$TEMP_DIR/stdin" || fail "exported DB_WEB_USER did not win"

# The web user must not be the owner, or the owner would be demoted.
if run_apply "$TEMP_DIR/password.txt" "$TEMP_DIR/team.env" DB_USER=same_role DB_WEB_USER=same_role; then
  fail "identical owner and web user were accepted"
fi
[[ ! -e "$TEMP_DIR/args" ]] || fail "psql ran with identical owner and web user"

printf 'PASS: apply_postgres_roles.sh keeps the password on stdin and resolves settings correctly\n'
