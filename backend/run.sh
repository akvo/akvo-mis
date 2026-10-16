#!/usr/bin/env bash
# shellcheck disable=SC2155

./wait-for-it.sh -h "${DB_HOST}" -p 5432 -- echo "Database is up and running"

rm -f /var/tmp/cache/*.djcache 2>/dev/null || true

set -eu
pip -q install uv==0.13.0
uv sync --locked --inexact
pip check

python manage.py migrate
python manage.py generate_config
python manage.py runserver 0.0.0.0:8000
