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

The web container listens on `127.0.0.1:8000`; put Nginx in front of it as planned. The proxy must pass `X-Forwarded-Proto: https` and `X-Real-IP $remote_addr`; the admin sign-in limit depends on the second (see [Admin accounts and sign-in](#admin-accounts-and-sign-in)). Nginx should serve `/static/` directly when practical; WhiteNoise is included as a fallback.

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

Never run `seed_demo` against real team content.

## Site content

- Team members, leads, cars, sponsors, sponsorship tiers, events, and extra gallery photos are managed in `/admin/`. Members appear on the roster only once they have a section; several co-leads per section are supported.
- **News posts** (`/news/`, with an RSS feed at `/news/feed.xml`) are written in `/admin/` → Posts → Add post. Type a title (the web address fills in), a one-line summary, and the body in Markdown; the box has a short cheat sheet above it. New posts are drafts. Save and continue editing, open the **Preview** link to check it, then tick **Published**. Pick a future date to schedule a post, or use the list's *Publish selected posts now* action. Photos are links to images already hosted somewhere (the same way roster and gallery photos work); add a description for each so everyone can read the post. Staff can open drafts by address; visitors get a 404. Post text is sanitized, so scripts and `javascript:` links in a pasted post are dropped, and `#` headings render as `h2` because the title is the page heading.
- Sponsor logos are trademarks. Only publish a sponsor's name and logo with their written permission (a sponsorship agreement or an email from them), use the file they supply unaltered, and follow their brand guidelines. Do not imply endorsement beyond the sponsorship. Deactivate the sponsor in `/admin/` to remove it from every page.
- The sponsorship proposal PDF lives in `static/documents/` and its cover preview in `static/images/sponsorship-cover.webp`. Replace both together when the proposal changes.
- Built-in team photos and short program copy (roadmap, metrics, engineering sections) live in `static/images/` and `team/content.py`.

## Admin accounts and sign-in

`/admin/` is the only place anyone signs in, so it has two protections. Five wrong passwords lock that username out from that address for 30 minutes, and staff also enter a six-digit code from an authenticator app (any TOTP app works). The code requirement is on in production and off in local development; `DJANGO_ADMIN_REQUIRE_OTP` controls it.

Accounts are set up from the server, never through the admin, so turning this on does not depend on being able to sign in. Run these in the checkout on the server:

```bash
docker compose exec web python manage.py admin_mfa status            # who is set up
docker compose exec web python manage.py admin_mfa enroll <username> # add an authenticator
docker compose exec web python manage.py admin_mfa unlock <username> # clear a lockout
docker compose exec web python manage.py admin_mfa reset <username>  # lost phone or departed admin
```

`enroll` prints a setup key and an `otpauth://` link. Type the key into the authenticator app, then enter the code the app shows. The key is a secret, so clear the terminal's scrollback afterwards. Use `enroll <username> --replace` to swap in a new phone. Signing in takes one step: username, password, and the code in the "OTP Token" box.

- **Locked out.** Wait 30 minutes, or run `admin_mfa unlock <username>`. The lockout is per username and address, so one person's mistakes do not stop another admin.
- **"Verification of the token is currently disabled."** Several wrong codes were entered for that account. Run `admin_mfa unlock <username>`. If you did not enter them, change that user's password too: someone knows it.
- **Lost phone.** `admin_mfa reset <username>`, then `admin_mfa enroll <username>`.
- **Emergency only.** If nobody can sign in, set `DJANGO_ADMIN_REQUIRE_OTP=false` in `.env` and run `docker compose up -d web`. That drops the code check but keeps the lockout. Turn it back on as soon as the accounts are fixed.

### First deploy of this change

Do these in the normal [update steps](#updating-production), so nobody is locked out:

1. Run steps 1–6 (back up, pull, build, migrate). Migrating creates the sign-in tables.
2. **Before step 7**, enroll every admin, then check that none are missing. The `migrate` image already has the new code, and `web` is still serving the old one:

   ```bash
   docker compose --profile ops run --rm migrate python manage.py admin_mfa enroll <username>
   docker compose --profile ops run --rm migrate python manage.py admin_mfa status
   ```

3. Add the `X-Real-IP` line to Nginx (below), run `nginx -t`, and reload it.
4. Run step 7. Existing admin sessions are sent to the sign-in page once.
5. Sign in with a code. Then enter one wrong password from your own phone and run `docker compose exec web python manage.py axes_list_attempts`. It must show your public address, not one starting with `172.`. If it shows `172.`, Nginx is not sending `X-Real-IP`.

### Nginx

Every location that proxies to the site needs all three header lines; `proxy_set_header` is not inherited by a sibling `location`. `X-Real-IP` replaces any value the visitor sent, which is what makes the address trustworthy.

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Real-IP $remote_addr;
}

# Optional: slow password guessing down before it reaches Django (the zone line goes in http {}).
limit_req_zone $binary_remote_addr zone=admin_login:10m rate=10r/m;
location = /admin/login/ {
    limit_req zone=admin_login burst=5 nodelay;
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Django trusts `X-Real-IP` the same way it trusts `X-Forwarded-Proto`, so only Nginx should be able to reach the web container. Compose publishes its port on `127.0.0.1` only, and the database is the only other container on the Compose network. If a CDN or another proxy sits in front of Nginx, `$remote_addr` is that proxy: set `real_ip_header` and `set_real_ip_from` first so it holds the visitor's address. To limit `/admin/` to known networks, add `allow <address>; deny all;` to a `location /admin/` block. A wrong or missing `X-Real-IP` never opens a hole in the password check; it only makes the lockout less precise.

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
3. Archive outgoing members: in the Team members list, tick them and choose **Archive selected members**. They leave the roster but their record stays; do not delete historical records. Remove their admin sign-in codes with `admin_mfa reset <username>` and untick **Active** on their user.
4. Update sponsors, events, and optional gallery additions in `/admin/`; the built-in team photos ship with the site.
5. Rotate the technical owner, deployment secrets, and the notes in this README.
