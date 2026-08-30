#!/usr/bin/env bash
# Dump the database locally, then push the newest dump offsite to Google Drive.
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose run --rm web python manage.py backup
docker compose run --rm web python manage.py backup_push
