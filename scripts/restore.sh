#!/usr/bin/env bash
# Restore the database from a local gzipped backup (newest slot by default).
# Pass through options, e.g. --file previous or --noinput.
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose run --rm web python manage.py restore "$@"
