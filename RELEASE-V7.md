# Electric Sting Racing — sponsorship and leads update

The sponsors page includes the supplied 2026–2027 proposal, a cover preview,
and separate view/download actions. Its benefit comparison now reflects the
proposal, including website recognition, social media, progress updates,
event invitations, recruiting, and merchandise. Those fields remain editable
through the Sponsorship Tier admin. Sponsorship inquiry links use the email
printed in the proposal: Electricsting@csus.edu.

The supplied trackside photo appears on the homepage and in the gallery.
Both the PDF and photo are included unchanged; the cover preview is generated
from the first page of the PDF. The existing neon theme, scroll reveals,
mobile navigation, and other gallery photos remain.

The roster now includes Business as a sixth section, and Suspension uses the
requested singular label. Migration 0007 adds or updates these nine leads:

| Section | Name | Role |
| --- | --- | --- |
| Business | Mizael Iniguez | Business Lead |
| High Voltage | Mirzett Evans IV | High Voltage Lead |
| Powertrain | Ben Israel Gurjar | Powertrain Lead |
| Powertrain | Micheal Quezada | Powertrain Lead |
| Powertrain | Juan Magana | Powertrain Lead |
| Low Voltage/Controls | Branden Pavon | Low Voltage/Controls Lead |
| Low Voltage/Controls | Jay Tolentino | Low Voltage/Controls Lead |
| Frame | Sergio Torres Guzman | Frame Lead |
| Suspension | Jacqueline Garcia | Suspension Lead |

Existing matching profiles keep their biographies, photos, and class years.
Co-leads are supported and marked with the Section lead badge. Business is
spelled correctly; personal names are kept as supplied. The data migration
preserves custom sponsorship fields, amounts, disabled packages, and unrelated
members. Do not run `seed_demo` against real team content.

## Apply to your server

Keep your existing database and environment configuration, install the
requirements if needed, then run from the Website folder:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

Restart the application. Database changes are required for the leads and the
updated benefit fields to appear. This archive contains source and static
assets; virtual environments, Git internals, test databases, and generated
staticfiles are omitted. See README.md for fresh setup and deployment.

## Validation

- Django system checks and migration consistency checks passed.
- All 39 repository tests passed on SQLite and embedded PostgreSQL 18.3
  (PGlite), including all migration tests. Native PostgreSQL 16 was unavailable
  in this environment; the GitHub Actions PostgreSQL job remains the native check.
- The original PostgreSQL varchar(40) failure was reproduced. The corrected
  migration recovered from 0006, repeated without duplicate leads, and the
  entire team migration chain reversed and reapplied successfully.
- A regression test validates every proposal value against the historical
  schema at migration 0007, so SQLite cannot hide string-length failures.
- All 12 frontend behavior tests passed.
- Source checks, restore-safety checks, and staging-smoke checker tests passed.
- Home, team, sponsors, and gallery pages returned 200 with the collected
  production static manifest. The served PDF and photo matched the attachments
  byte for byte; all nine lead profiles rendered on the roster.
- Browser layout verification was unavailable in this environment. Responsive
  CSS and the existing mobile behavior are included.

Page source release marker: `es-sponsorship-v7`.

## PostgreSQL migration correction

The original Bronze description had 44 characters but logo_size allows 40.
Migration 0007 now stores "Extra small on secondary bodywork" (33 characters),
retaining both size and location. Editing the failing 0007 is necessary because
adding a later migration alone cannot resolve a failure earlier in the chain.

Migration 0008 normalizes only the exact original overlong Bronze default on
SQLite installations that had already applied 0007. It preserves custom text
and is idempotent. All other sponsorship details remain in the full PDF.

For a checkout already containing the previous v7 release, the fix changes
team/migrations/0007_requested_leads_and_proposal_benefits.py and team/tests.py,
and adds team/migrations/0008_normalize_bronze_logo_description.py.
Apply these source changes, commit and push them, then rerun CI. The failed
PostgreSQL migration rolled back; normal `migrate` retries it. No `--fake`,
database reset, or deletion is required.
