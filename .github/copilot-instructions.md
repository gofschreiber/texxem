# Project Guidelines — Texxem (Betriebskostenabrechnung)

This project implements the business specification in [specification.md](../specification.md), a German-language
domain specification for utility cost billing ("Betriebskostenabrechnung") for a small multi-family house.

## Process

- **Specification is the source of truth.** Whenever a feature, table, business rule, or technical decision is
  added or changed, update [specification.md](../specification.md) in the same change (new/adjusted section,
  not just code). Never let code and specification drift apart.
- **No assumptions.** If a requirement, naming, data type, business rule, or technical detail is not explicitly
  covered by the specification or by prior decisions recorded here, ask the user before implementing. Do not
  guess silently.
- Record every confirmed technical decision in this file (if it's a cross-cutting convention) or in
  `specification.md` (if it's a domain/business decision).

## Language Conventions

- **specification.md**: German. All existing and future content stays in German.
- **UI (templates, user-facing text, labels, validation messages)**: German, using the correct German tenancy-law
  / BetrKV terminology already established in the specification (e.g. "Mietverhältnis", "Nebenkostenabrechnung",
  "Wohneinheit").
- **Code** (Python identifiers: classes, functions, variables, module names, comments): English.
- **Database schema** (table names, column names): German, exactly as defined in `specification.md`
  (e.g. table `mietverhaeltnis`, column `einzugsdatum`). SQLAlchemy models use English class/attribute names and
  map explicitly to the German `__tablename__` / column names, e.g.:

  ```python
  class TenancyAgreement(db.Model):
      __tablename__ = "mietverhaeltnis"

      id = db.Column("id", db.Integer, primary_key=True)
      move_in_date = db.Column("einzugsdatum", db.Date, nullable=False)
  ```

## Tech Stack

- **Language/Runtime**: Python 3.12
- **Web framework**: Flask, using the application factory pattern (`create_app()`)
- **Database**: MariaDB (`utf8mb4` / `utf8mb4_unicode_ci`), driver PyMySQL (`mysql+pymysql://`)
- **ORM**: SQLAlchemy via Flask-SQLAlchemy
- **Migrations**: Alembic via Flask-Migrate
- **Auth**: Flask-Login; password hashing via `werkzeug.security`
  (`generate_password_hash` / `check_password_hash`). Maps to the `benutzer` table (single role, no
  fine-grained permission system needed).
- **Dependency management**: pip + venv, pinned in `requirements.txt` (no Poetry/Pipenv)
- **Tests**: pytest, under `tests/`
- **Linting/formatting**: ruff (`ruff check`, `ruff format`)

## Architecture

Planned project layout:

```
.github/
  copilot-instructions.md
app/
  __init__.py          # application factory (create_app)
  extensions.py        # db, login_manager, migrate instances
  config.py            # loads/validates config.json into a Config object
  logging_setup.py      # configures the shared logger (see "Logging" below)
  models/               # one module per table, English class names, German __tablename__/columns
  blueprints/            # one blueprint package per functional area (auth, stammdaten, kosten,
                          # zaehler incl. the meter-reading REST API, abrechnung, ...)
  templates/            # Jinja2 templates, German UI text
  static/
migrations/              # Alembic migration scripts
tests/
log/                      # runtime log files (see "Logging"), directory tracked via .gitkeep,
                           # log file contents are gitignored
uploads/                   # Belege (receipt) file storage, directory tracked via .gitkeep,
                            # contents are gitignored
config.json                # single configuration file, see "Configuration" (committed to git)
requirements.txt
wsgi.py                     # WSGI entry point for the app server behind the reverse proxy
specification.md
```

Adjust/extend this layout as the implementation grows, but keep one blueprint per functional area and one
model module per table.

## Configuration

- All configuration data (DB credentials, Flask secret key, logging settings, upload directory, etc.) lives in a
  **single JSON file**, `config.json`, at the project root.
- `config.json` **is committed to git** — this is a deliberate decision by the project owner (not the usual
  `.gitignore` + example-template pattern). Do not introduce a separate `.env` mechanism or split config across
  multiple files.
- All code reads configuration through one central module (`app/config.py`); do not read `config.json` or
  environment variables directly from other modules.
- Suggested baseline schema (extend as new settings are needed — keep it flat and explicit, avoid growing random
  top-level keys without a clear grouping):

  ```json
  {
    "secret_key": "...",
    "database": {
      "host": "localhost",
      "port": 3306,
      "name": "texxem",
      "user": "...",
      "password": "..."
    },
    "logging": {
      "directory": "log",
      "level": "DEBUG",
      "retention_count": 5
    },
    "uploads": {
      "directory": "uploads"
    }
  }
  ```

## Logging

- **Shared log file across all modules**: every module obtains its logger via `logging.getLogger(__name__)`;
  there is no per-module log configuration. The root logger is configured once, centrally, in
  `app/logging_setup.py`, and all module loggers propagate to it.
- **New file per application start**: each time the application starts, a new log file is created with the
  start timestamp in its filename, e.g. `log/app_20260101_153000.log` (`%Y%m%d_%H%M%S`). This file *is* the "new
  block" for that run — do not additionally rotate by size or write separator lines into a shared growing file.
- **Location**: `log/` subdirectory of the project root.
- **Retention**: keep at most the 5 most recent log files. On each startup, before creating the new file, delete
  the oldest files beyond the 4 most recent existing ones, so that after startup exactly 5 files remain
  (4 previous + 1 new).
- Use a detailed format that includes timestamp, level, logger/module name, and message (e.g.
  `%(asctime)s %(levelname)-8s %(name)s: %(message)s`), and log generously across all modules (requests,
  business-rule decisions, DB writes, errors) — logging must be detailed enough to reconstruct what happened
  during a run.
- Log level and retention count are configurable via `config.json` (see "Configuration").

## Web UI Conventions

The UI is specified in [specification.md](../specification.md), sections 10–19 (Phase 2). Cross-cutting rules:

- **One central stylesheet**, `app/static/css/app.css`. No `style` attributes, no `<style>` blocks, no per-page CSS, no
  CSS frameworks/CDNs. Colours/spacing/fonts are CSS custom properties (design tokens); templates only set classes
  from the component catalog (spec 17.3).
- **Uniform CRUD pattern** for every entity (spec 12): same URL scheme (`/<ressource>/neu`, `/<id>/bearbeiten`,
  `/<id>/loeschen`), same row/node actions (Anzeigen · Bearbeiten · Löschen), same form buttons (Speichern ·
  Abbrechen), two-step delete with dependency check. Implement via shared CRUD helpers and Jinja macros
  (`macros/forms.html`, `tables.html`, `tree.html`, `actions.html`, `icons.html`) — do not hand-write per-entity variants.
- **Multi-level data is shown as a collapsible tree** (`<details>`/`<summary>`, works without JS); single-level data
  as a table.
- Pages must work without JavaScript; JS is progressive enhancement only (vanilla, no libraries, no CDNs).
- Every write is `POST` with a CSRF token (Flask-WTF `CSRFProtect`); UI text is German.

## Reverse Proxy / Security

- The app runs behind a reverse proxy that terminates TLS/HTTPS and forwards plain HTTP to Flask.
- The proxy is responsible for setting correct forwarding headers; **no `ProxyFix` middleware** is used in the
  Flask app.
- Session cookies are nonetheless hardened regardless of the proxy: `SESSION_COOKIE_SECURE = True`,
  `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = "Lax"`.

## File Uploads

- Receipts (`Belege`, table `kosten_beleg`) are stored on the local filesystem.
- The storage directory is configurable via `config.json` (`uploads.directory`, default `./uploads`); the
  `speicherreferenz` column stores the path/key relative to that directory.
- No hard file-size or MIME-type restriction in the initial implementation; revisit if/when needed.

## Build and Test

Once the project is scaffolded:

- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run dev server: `flask --app wsgi run`
- Apply migrations: `flask db upgrade`
- Create the first operator account: `flask --app wsgi create-user <username> <email>`
- Run tests: `pytest`. Tests run the app in **test mode** (`create_app(test_mode=True)`): database
  `<database.name>_test` (`texxem_test`, must exist and be accessible to the configured DB user), `uploads/_test/`,
  log files `app_<timestamp>_test.log`. The test session rebuilds the test database via the Alembic migrations
  (`downgrade base` → `upgrade`) and resets the data before every test. Test mode refuses to start on a database whose
  name does not end in `_test`. Manual try-out: `flask --app wsgi_test db upgrade && flask --app wsgi_test run`.
- Lint/format: `ruff check .` / `ruff format .`

## Service (systemd)

- Production runs as `texxem.service` (gunicorn, `0.0.0.0:8000`, reachable from the LAN, `Restart=on-failure`). The unit template lives in
  `deploy/texxem.service`; install/update with
  `sudo cp deploy/texxem.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart texxem`.
- After code changes or `flask db upgrade`: `sudo systemctl restart texxem`. Logs: `journalctl -u texxem -f`.
- Keep `--preload` in the unit: `create_app()` creates the per-start log file and must run once, not per worker.

## Database Migrations

- Schema changes are made only through Alembic migrations in `migrations/versions/` (`flask db migrate` +
  review, then `flask db upgrade`). Catalog seed data (`kostenart`, `verteilerschluessel`, `zaehlertyp`) lives
  in the initial migration.
- The constraint naming convention is defined centrally in `app/extensions.py`; do not name constraints ad hoc.

## Testing Conventions

- **Drive tests through the web interface** (`tests/ui.py`: loads the form for its CSRF token, posts with Referer,
  follows redirects) and **verify the result in the database** with an independent query (`query` fixture, fresh
  connection). Direct DB writes are only for preparation that the UI cannot do (e.g. `SCHNITTSTELLE` readings).
- Create test data through the UI with the helpers in `tests/helpers.py` (form field names are the German column names).
- Do not keep an app context open around client requests (it would share the DB session with the app).
- `tests/test_ui_consistency.py` guards the UI conventions above (uniform actions/forms, tree vs. table, single
  stylesheet, no inline styles, every used CSS class defined). New pages/entities must keep these tests green.
