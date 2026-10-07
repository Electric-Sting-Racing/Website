# Electric Sting — sponsorship release v6

The original sponsorship packages are restored automatically by migration 0005:

| Package | Amount | Badge | Social posts | Car logo | School tour | Merch logo |
| --- | --- | --- | --- | --- | --- | --- |
| Bronze | $500+ | Bronze Leaf | 1 | Extra small | No | No |
| Silver | $1,500+ | Silver Tulip | 1 | Small | No | Yes |
| Gold | $3,500+ | Gold Rose | 2 | Medium | Yes | Yes |
| Platinum | $5,000+ | Platinum Orchid | 3 | Large | Yes | Yes |

Amounts and benefits match the original uploaded project. No demo members,
events, or sponsor companies are created. Existing package edits and disabled
packages are preserved; missing packages are added. Reversing the migration keeps
the packages, so subsequent editorial changes are not deleted.

The restore verification script checks the connected database name before
running its destructive restore command. It requires a disposable target name
ending in `_restore` and rejects a matching `DATABASE_URL` database.
Production settings also reject Django signing keys shorter than 50 characters
and the example database-password placeholder.

Public pages no longer tell visitors to add content through Django admin.
Empty calendars and partner lists now use visitor-facing messages. The v5 neon
theme, supplied logo, five roster sections, leads, mobile layout, lazy loading,
and scroll effects remain included.

## Upgrade

Back up your existing database. Extract this ZIP to a new folder, keep your real
database/configuration, activate your environment, and run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

Restart your server from the new project folder. For local non-Docker startup,
follow RELEASE-V5.md; this archive's folder is electric-sting-v6 and its page
source release marker is es-sponsorship-v6. Do not run seed_demo on real content.

Source/archive checks, JavaScript behavior tests, and restore-target safety
tests are included.
Django tests are included for package restoration, preservation of edits, and
public empty pages, but Django and browser rendering remain unavailable in the
delivery environment. Run `python manage.py test` before deployment.
