# Electric Sting Racing

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

Create the three local secret files only if your deployment host is not injecting them through a secret manager:

```bash
cp .env.example .env
mkdir -p secrets
openssl rand -base64 48 > secrets/django_secret_key.txt
openssl rand -base64 32 > secrets/db_password.txt
openssl rand -hex 32 > secrets/db_web_password.txt
chmod 600 secrets/*.txt
```

Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` in `.env`, then run:

```bash
docker compose up -d --wait db
bash scripts/apply_postgres_roles.sh
docker compose --profile ops run --rm migrate
docker compose up -d web
```

The database has two roles. `fsae_app` (`DB_USER`) owns the tables and is used only by `migrate` and backups. The site connects as `fsae_web` (`DB_WEB_USER`), which can read and write rows but cannot create, alter, or drop anything and cannot connect to other databases. `scripts/apply_postgres_roles.sh` creates it from `scripts/postgres/web_role.sql`. It reads `DB_NAME`, `DB_USER`, and `DB_WEB_USER` from `.env`, so you do not need to export anything, and it is safe to run again. If you skip it, the site cannot reach the database and `/healthz/` returns `503` with "password authentication failed for user fsae_web".

The script also removes the default public access to every other database on the server, so run it again after creating one (for example a restore database). Tables added by later migrations are granted to `fsae_web` automatically, as long as migrations run through the `migrate` service (as the owner). If `permission denied for table` ever appears in the logs, run `bash scripts/apply_postgres_roles.sh` again.

The web container listens on `127.0.0.1:8000`; put Nginx in front of it as planned. The proxy must pass `X-Forwarded-Proto: https`. Nginx should serve `/static/` directly when practical; WhiteNoise is included as a fallback.

The database is not published to the host. Compose uses a named PostgreSQL volume, waits for a database health check, and keeps the one-shot migration job separate from the web process. Run migrations explicitly during releases before switching traffic.

## Updating production

There is no automatic deploy. CI tests every push and builds the image, but nothing publishes it. Production is updated by hand on the server that runs the Docker Compose stack from this repository, by whoever holds SSH access to it. Each step below is run on that server unless stated otherwise.

1. **Get the change onto `main`.** Open a pull request, wait for the `CI` workflow to pass, and merge. Deploy only commits that are on `main` and green in CI.

2. **Connect to the server and go to the checkout.**

   ```bash
   ssh <deploy-user>@<production-host>
   cd /path/to/Website
   ```

3. **Back up the database first.** The database is not published to the host, so run `pg_dump` inside the `db` container. Keep the file somewhere off the server as well.

   ```bash
   mkdir -p backups
   docker compose exec -T db pg_dump -U fsae_app -d fsae --format=custom --no-owner --no-privileges \
     > "backups/fsae-$(date -u +%Y%m%dT%H%M%SZ).dump"
   ```

4. **Pull the new version.** Do not edit files on the server; `.env` and `secrets/` are ignored by Git and survive the pull.

   ```bash
   git fetch origin
   git checkout main
   git pull --ff-only origin main
   git log -1 --oneline   # note this commit in case you need to roll back
   ```

5. **Build the new images.** `collectstatic` runs during the build, so static files are part of the image. `web` and `migrate` are separate images, so build both; otherwise the migration step runs the old code and reports "No migrations to apply".

   ```bash
   docker compose --profile ops build --pull web migrate
   ```

6. **Run migrations.** This uses a one-shot container and leaves the current site serving traffic until the next step.

   ```bash
   docker compose --profile ops run --rm migrate
   ```

   A migration that fails on PostgreSQL rolls back by itself. Fix the cause, pull the fix, and run this step again. Do not use `--fake`, reset the database, or delete data to get past a failure.

7. **Switch traffic to the new image.**

   ```bash
   docker compose up -d web
   docker compose ps
   ```

   If Nginx serves `/static/` from a host directory instead of proxying to WhiteNoise, refresh that directory from the new image:

   ```bash
   docker compose cp web:/app/staticfiles/. /path/nginx/serves/as/static/
   ```

8. **Verify.** The health check needs the same `Host` and `X-Forwarded-Proto` headers the proxy sends.

   ```bash
   docker compose logs --tail=50 web
   curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: <public-hostname>' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/healthz/
   curl -s -o /dev/null -w '%{http_code}\n' https://<public-hostname>/
   ```

   Expect `200` from both. Then load the home, team, sponsors, and gallery pages in a browser. For a bigger release, run the `Staging audit` workflow in GitHub Actions against the public URL; it checks `/healthz/`, Lighthouse, and accessibility.

9. **Clean up.** Old images accumulate on the server.

   ```bash
   docker image prune -f
   ```

### Rolling back

Check out the commit noted in step 4, rebuild, and restart:

```bash
git checkout <previous-commit>
docker compose --profile ops build web migrate
docker compose up -d web
```

This only reverts the code. If the release added a migration and the old code cannot run against the new schema, reverse it before restarting, naming the last migration the old code shipped with:

```bash
docker compose --profile ops run --rm migrate python manage.py migrate team <previous-migration-number>
```

Restoring the backup from step 3 is the last resort; it discards every admin change made since the backup.

### Without Docker

If the server runs the app from a virtual environment behind a process manager instead of Compose, the equivalent steps after `git pull --ff-only` are:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart <gunicorn-service>
```

Run the same role setup against your PostgreSQL server as its owner with `PSQL_COMMAND="psql -h <host>" bash scripts/apply_postgres_roles.sh`. Run gunicorn with `DB_USER=fsae_web` and the web password, and run `migrate` with the owner's credentials.

Never run `seed_demo` against real team content.

### Splitting the database roles (one time, servers set up before this change)

Until now the site connected as `fsae_app`, the superuser that owns everything. This switches it to `fsae_web`. Downtime is only the usual `web` container recreate, about 5 to 15 seconds. PostgreSQL is not restarted, and no rows or tables are touched; only roles and permissions change.

```bash
# 0. Back up first (step 3 above).
# 1. Create the web password (hex only).
openssl rand -hex 32 > secrets/db_web_password.txt && chmod 600 secrets/db_web_password.txt
# 2. Pull and build as usual (steps 4 and 5). The running site is not affected yet.
# 3. Create the role and grants. The site keeps running as fsae_app meanwhile. Safe to repeat.
bash scripts/apply_postgres_roles.sh
# 4. Prove the role is restricted. Replace fsae if DB_NAME differs in .env.
docker compose exec -T -e PGUSER=fsae_web -e PGDATABASE=fsae db sh -s < scripts/check_postgres_roles.sh
# 5. Switch the site to the new role.
docker compose up -d web
# 6. Verify: the site connects as fsae_web and works.
docker compose exec -T db psql -U fsae_app -d fsae -Atc \
  "select usename, count(*) from pg_stat_activity where datname = 'fsae' group by 1"
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: <public-hostname>' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/healthz/
```

Then edit and save any record in `/admin/`. Step 4 needs no password because the container's local socket trusts its users. The check fails if `fsae_web` can create tables, is a superuser, lacks access to any table, or can connect to another database; the message says which.

To point the site back at the owner, check out the previous commit and run `docker compose up -d web`. The old compose file uses `fsae_app` and `db_password`, and the extra role is harmless. To also remove the role, run this only after `web` no longer uses it:

```bash
docker compose exec -T db psql -X -v ON_ERROR_STOP=1 -U fsae_app -d fsae < scripts/postgres/web_role_rollback.sql
```

It stops without changing anything if `fsae_web` owns any object, because dropping the role would delete them.

## Site content

- Team members, leads, cars, sponsors, sponsorship tiers, events, and extra gallery photos are managed in `/admin/`. Members appear on the roster only once they have a section; several co-leads per section are supported.
- **News posts** (`/news/`, with an RSS feed at `/news/feed.xml`) are written in `/admin/` → Posts → Add post. Type a title (the web address fills in), a one-line summary, and the body in Markdown; the box has a short cheat sheet above it. New posts are drafts. Save and continue editing, open the **Preview** link to check it, then tick **Published**. Pick a future date to schedule a post, or use the list's *Publish selected posts now* action. Photos are links to images already hosted somewhere (the same way roster and gallery photos work); add a description for each so everyone can read the post. Staff can open drafts by address; visitors get a 404. Post text is sanitized, so scripts and `javascript:` links in a pasted post are dropped, and `#` headings render as `h2` because the title is the page heading.
- Sponsor logos are trademarks. Only publish a sponsor's name and logo with their written permission (a sponsorship agreement or an email from them), use the file they supply unaltered, and follow their brand guidelines. Do not imply endorsement beyond the sponsorship. Deactivate the sponsor in `/admin/` to remove it from every page.
- The sponsorship proposal PDF lives in `static/documents/` and its cover preview in `static/images/sponsorship-cover.webp`. Replace both together when the proposal changes.
- Built-in team photos and short program copy (roadmap, metrics, engineering sections) live in `static/images/` and `team/content.py`.

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
RESTORE_DATABASE_URL='postgresql://fsae_app@restore-host:5432/fsae_restore' \
bash scripts/restore_test_postgres.sh
```

Keep the password out of the URL: a password in a connection string shows in the process list while the restore runs and stays in shell history. Provide it through a `~/.pgpass` file, or `read -rs PGPASSWORD && export PGPASSWORD` in the same shell first. The script warns if it sees a password in either URL.

Before `pg_restore --clean`, the script checks the connected target database name. It must end in `_restore`; when `DATABASE_URL` is set, a target with the same database name is refused. Use a dedicated disposable database and do not point it at production.

Dumps leave out grants (`--no-privileges`), so after restoring into production run `bash scripts/apply_postgres_roles.sh` again to give `fsae_web` its access. Default privileges also cover tables that `pg_restore` creates as the owner, but running it again is harmless. Backups keep using the owner (`PGUSER=fsae_app`), not `fsae_web`.

## Security headers

Every response carries a Content Security Policy and a Permissions-Policy (`fsae_site/middleware.py`), on top of HSTS, `nosniff`, `X-Frame-Options: DENY`, and a same-origin referrer policy. The policy blocks inline scripts and styles, so put new JavaScript in `static/js/` and new CSS in `static/css/`; a test fails if a template gains an inline `<script>`, `<style>`, `style=`, or `on…=` handler. Images may come from any `https:` URL because roster, sponsor, and gallery photos are entered in the admin. `/admin/` only gets the directives that cannot break Django's own admin pages.

To try a stricter change safely, set `DJANGO_CSP_REPORT_ONLY=true`: browsers then log violations in the console without blocking anything. Allowed font hosts are listed in `CSP_STYLE_HOSTS` and `CSP_FONT_HOSTS` in `fsae_site/settings.py`; empty them once fonts are self-hosted. Session and CSRF cookies use the `__Host-` prefix in production, so the first deploy signs everyone out once. Admin sessions last 12 hours (`DJANGO_SESSION_COOKIE_AGE`), and requests that declare a body over 1 MiB get a 413 before reaching any view (nothing on the site accepts file uploads).

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
2. Add the new season's `Car` record and tick **current**; the previous current car is cleared automatically. The car form's "Kept for later" section lists fields the public pages do not show yet, and you can leave them empty.
3. Archive outgoing members: in the Team members list, tick them and choose **Archive selected members**. They leave the roster but their record stays; do not delete historical records.
4. Update sponsors, events, and optional gallery additions in `/admin/`; the built-in team photos ship with the site.
5. Rotate the technical owner, deployment secrets, and the notes in this README. To rotate the web database password, write a new `secrets/db_web_password.txt` (`openssl rand -hex 32`), run `bash scripts/apply_postgres_roles.sh`, then `docker compose up -d --force-recreate web`.
