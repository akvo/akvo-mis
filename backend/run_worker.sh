#!/usr/bin/env bash
# shellcheck disable=SC2155

set -e
pip -q install uv==0.13.0
uv sync --frozen --inexact
pip check

if [[ -v FREEZE ]]; then
  tail -f /dev/null
fi

python manage.py qcluster
