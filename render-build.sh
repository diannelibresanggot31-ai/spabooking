#!/usr/bin/env bash
set -euo pipefail

# Install main requirements
pip install --no-cache-dir -r requirements.txt
# Install extra deployment requirements if present
if [ -f requirements-extra.txt ]; then
  pip install --no-cache-dir -r requirements-extra.txt
fi

# Collect static files and run migrations
python manage.py collectstatic --noinput
python manage.py migrate --noinput
