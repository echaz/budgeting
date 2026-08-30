# Operations

How to run, configure, back up, restore, and work with the app. Everything
runs through Docker Compose (`db` = Postgres 17, `web` = Django).

## Configuration & environment

Settings read the database connection from environment variables, defaulting to
a local dev setup. Copy `.env.example` to `.env` (gitignored) and fill in.

### Database password: `PS_PASSWORD`

The database password is read from **`PS_PASSWORD`**, not `POSTGRES_PASSWORD`.

Why: Docker Compose gives shell environment variables precedence over `.env`.
A shell that exports `POSTGRES_PASSWORD` (common) would silently override the
project's `.env`, causing confusing auth failures. Using a project-specific
name (`PS_PASSWORD`) that the shell does not export makes `.env` authoritative.

- `.env` sets `PS_PASSWORD`.
- `docker-compose.yml` feeds it to both services via `${PS_PASSWORD:-postgres}`.
- The `db` service's *internal* variable is still `POSTGRES_PASSWORD` (the
  official `postgres` image requires that exact name); it is sourced from
  `${PS_PASSWORD}`.

Note: the `postgres` image only applies the password when it initializes an
**empty** data directory. Changing `PS_PASSWORD` after the volume exists does
not change the stored password — drop the volume to re-initialize:

```
docker compose down -v && docker compose up -d db
```

### Google Drive backups

`GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`, `GDRIVE_REFRESH_TOKEN`,
`GDRIVE_FOLDER_ID` — see `.env.example` and `scripts/setup_gdrive.py`.

## Running

```
docker compose up -d              # start db + web (http://localhost:8000)
docker compose logs -f web        # tail logs
docker compose down               # stop (keeps data); add -v to wipe the DB
```

Run management commands in a throwaway container (reads current `.env`, does
not depend on the long-running `web` container):

```
docker compose run --rm web python manage.py <command>
```

## Database migrations

```
docker compose run --rm web python manage.py migrate
```

## Imports

Bank/card statements are imported from CSV via the importers in `scrapers/`. See
`docs/IMPORTS.md` for the per-source parsers and the idempotency (re-run safety)
strategy.

## Users & authentication

Auth uses Django's built-in `User` model and standard auth views (no custom
user model, no self-signup).

- `/` — login-protected home page.
- `/accounts/login/`, `/accounts/logout/`, password change/reset — from
  `django.contrib.auth.urls`.
- Redirects: `LOGIN_URL=login`, `LOGIN_REDIRECT_URL=home`,
  `LOGOUT_REDIRECT_URL=login`.
- Templates: `core/templates/registration/login.html`, `core/templates/home.html`.
  Logout is a POST (required since Django 5).

Create users:

```
docker compose run --rm web python manage.py createsuperuser
```

Or from the shell (uses the password hasher — never set `.password` directly):

```python
from django.contrib.auth import get_user_model
get_user_model().objects.create_superuser("admin", "admin@example.com", "changeme")
```

## Backups

Two-stage: a local rotating dump, then an offsite push to Google Drive.

### Local dump — `backup`

```
docker compose run --rm web python manage.py backup
docker compose run --rm web python manage.py backup --force
```

- Health-checks the DB (aborts if down or in recovery), runs `pg_dump | gzip`,
  verifies the gzip, then atomically rotates: `backup_file1` -> `backup_file2`,
  new dump -> `backup_file1`.
- **Growth guard:** aborts (without rotating) if the new dump's *uncompressed*
  size is not larger than the previous `backup_file1` — backups are expected to
  grow, so a shrink or no-growth signals data loss or a bad dump. Skipped on the
  first backup (no previous file) and when the previous file is unreadable.
- `--force` skips only the growth guard; the DB health, empty-file, and gzip
  checks still run.

### Host-side dump without Django — `scripts/backup_host.py`

For dumping from the **host** without booting Django (the host virtualenv does
not carry `django_extensions`, so `manage.py` can't import settings there). Pure
stdlib; reproduces the same rotation, gzip integrity, and growth checks as the
`backup` command.

```
python scripts/backup_host.py [--force]            # host-native pg_dump over TCP
python scripts/backup_host.py --via-docker         # source the dump via the db container
```

- Connection settings come from the environment (loaded from `.env` when
  present): `POSTGRES_DB`, `POSTGRES_USER`, `PS_PASSWORD`, `POSTGRES_HOST`,
  `POSTGRES_PORT`, `BACKUP_DIR`. Host defaults point at `localhost:5433` (the
  published `db` port).
- `--via-docker` runs `pg_dump` inside the `db` container (unix-socket trust, no
  password) instead of connecting to the published port. Use it when something
  else already holds the host port (e.g. an SSH tunnel bound to `5433`), which
  makes a host-native TCP connection fail or hit the wrong server.

### Offsite push — `backup_push`

Pushes the newest local dump to a double-buffered Google Drive store (two slots
+ a manifest pointer; uploads to the inactive slot, verifies md5/size, then
flips the manifest).

```
docker compose run --rm web python manage.py backup_push
```

### Combined — `scripts/backup.sh`

Runs `backup` then `backup_push`, aborting if the dump fails. Cron-friendly.

```
./scripts/backup.sh
```

## Restore

`restore` is the destructive mirror of `backup`. It replays a local gzipped
`pg_dump` with `psql` (our dumps are plain SQL, so `psql`, not `pg_restore`),
after resetting the `public` schema. Local files only (no Drive pull yet).

```
./scripts/restore.sh                    # newest local backup (prompts first)
./scripts/restore.sh --file previous    # the prior slot
./scripts/restore.sh --file <path>      # an explicit .sql.gz
./scripts/restore.sh --noinput          # skip the confirmation
```

Under the hood: `docker compose run --rm web python manage.py restore [...]`.

## Dev shell

`shell_plus` (from `django-extensions`) auto-imports all models and common
Django helpers, and uses IPython:

```
docker compose run --rm web python manage.py shell_plus
```

Your host IPython config is mounted into the container: `docker-compose.yml`
maps `${HOME}/.ipython:/root/.ipython`, so your profile (and history) apply
inside the container. Add `:ro` to the volume if you don't want the container
writing back to your host config.
