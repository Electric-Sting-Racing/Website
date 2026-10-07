# Electric Sting Racing

For the restored sponsorship packages and public-page cleanup, start with [RELEASE-V6.md](RELEASE-V6.md). The neon theme, roster leads, scroll effects, mobile layout, and startup instructions are covered in [RELEASE-V5.md](RELEASE-V5.md).

A maintainable Django site for Sacramento State's Formula SAE Electric team. It includes the public site, a Django admin, PostgreSQL production support, structured logs, a database health endpoint, and deployment checks.

## Local development

The default settings are production-safe. Explicitly enable debug mode for local SQLite development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DJANGO_DEBUG=True
export DB_ENGINE=sqlite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the site and `/admin/` for content management.

The site works with an empty database. `python manage.py seed_demo` is optional
for a disposable development database only; it creates fictional example members
and should not be run against real team content.

## Production deployment

Production settings fail closed: `DEBUG` defaults to false, PostgreSQL and allowed hosts are required, and the Django secret key must be at least 50 characters. Example secret placeholders are rejected. The settings support secret-manager-mounted files through `DJANGO_SECRET_KEY_FILE` and `DB_PASSWORD_FILE`.

`.env.example` leaves HSTS `includeSubDomains` and `preload` disabled because those settings require every subdomain to remain HTTPS-only. Enable them in a real deployment only after verifying that condition. CI separately checks a strict HTTPS deployment profile with both options enabled.

Create the two local secret files only if your deployment host is not injecting them through a secret manager:

```bash
cp .env.example .env
mkdir -p secrets
openssl rand -base64 48 > secrets/django_secret_key.txt
openssl rand -base64 32 > secrets/db_password.txt
chmod 600 secrets/*.txt
```

Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` in `.env`, then run:

```bash
docker compose --profile ops run --rm migrate
docker compose up -d web
```

The web container listens on `127.0.0.1:8000`; put Nginx in front of it as planned. The proxy must pass `X-Forwarded-Proto: https`. Nginx should serve `/static/` directly when practical; WhiteNoise is included as a fallback.

The database is not published to the host. Compose uses a named PostgreSQL volume, waits for a database health check, and keeps the one-shot migration job separate from the web process. Run migrations explicitly during releases before switching traffic.

## Backups and restore testing

`pg_dump` custom-format backups are created by `scripts/backup_postgres.sh`. It uses standard PostgreSQL connection variables and keeps fourteen days by default. Prefer `PGPASSFILE` or a secret-manager-injected credential over putting a password in shell history:

```bash
PGHOST=db.example.internal \
PGPORT=5432 \
PGUSER=fsae_app \
PGDATABASE=fsae \
PGPASSFILE=/run/secrets/postgres_backup \
BACKUP_DIR=backups \
bash scripts/backup_postgres.sh
```

Copy backups to durable off-host storage. A backup is not considered useful until it has been restored. Test one into a dedicated, disposable database:

```bash
BACKUP_FILE=backups/fsae-20260101T000000Z.dump \
RESTORE_DATABASE_URL='postgresql://fsae_app:password@restore-host:5432/fsae_restore' \
bash scripts/restore_test_postgres.sh
```

Before `pg_restore --clean`, the script checks the connected target database name. It must end in `_restore`; when `DATABASE_URL` is set, a target with the same database name is refused. Use a dedicated disposable database and do not point it at production.

## Observability and operations

- `/healthz/` performs a database connection check and returns `200` only when the application can reach PostgreSQL; failures return `503` with `Cache-Control: no-store`.
- Point an external uptime monitor at `/healthz/` and alert on non-`200` responses or repeated container restarts.
- Gunicorn replaces `runserver` in the container and writes access/error logs to stdout/stderr for the platform log collector.
- Django request, security, and application logs use structured, timestamped console formatting.
- Set `SENTRY_DSN` to enable error reporting and tracing. Keep `SENTRY_TRACES_SAMPLE_RATE` conservative in production.
- The container runs as a non-root user and has a Docker health check.

## CI and staging quality gates

`.github/workflows/ci.yml` runs on pushes and pull requests. It provisions PostgreSQL, runs migrations and Django tests, runs `check --deploy --fail-level WARNING` against a strict HTTPS profile, audits Python dependencies with `pip-audit`, verifies a backup/restore cycle, and builds the Docker image. It also runs dependency-free source, restore-safety, and staging-smoke checker tests.

`.github/workflows/staging-audit.yml` is manually triggered with a public HTTPS staging URL. It first checks that the home page and database-backed `/healthz/` endpoint return successfully, then runs Lighthouse in three runs and axe-core accessibility checks. Lighthouse lab data covers LCP and CLS; measure INP with real-user monitoring or field data before launch because lab runs cannot fully represent it.

Run the same checks locally when the relevant tools are installed:

```bash
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True DJANGO_SECURE_HSTS_PRELOAD=True python manage.py check --deploy --fail-level WARNING
npx --yes @lhci/cli@0.14.0 autorun --config=lighthouserc.json --collect.url=https://staging.example.com
npx --yes @axe-core/cli@4.10.2 https://staging.example.com
```

## Annual handoff

1. Export or back up the production database and verify a restore.
2. Add the new season's `Car` record and mark only one car as current.
3. Archive outgoing members with `active=False`; do not delete historical records.
4. Update sponsors, events, and optional gallery additions in `/admin/`; the built-in team photos ship with the site.
5. Rotate the technical owner, deployment secrets, and the notes in this README.
