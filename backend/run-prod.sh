#!/usr/bin/env bash
# shellcheck disable=SC2155

set -eu

python manage.py migrate
python manage.py generate_sqlite >/dev/null &
python manage.py generate_config >/dev/null &
python manage.py download_all_administrations >/dev/null &
python manage.py generate_qr_code >/dev/null &
# Backfill and repair datapoint files; the worker repeats it hourly (APP-517)
python manage.py generate_data_json >/dev/null &

function log {
    echo "$(date +"%T") - START INFO - $*"
}

_term() {
    echo "Caught SIGTERM signal!"
    kill -TERM "$child" 2>/dev/null
}

trap _term SIGTERM

log Starting gunicorn in background
gunicorn mis.wsgi --workers 6 --timeout 300 --bind 0.0.0.0:8000 &

child=$!
wait "$child"
