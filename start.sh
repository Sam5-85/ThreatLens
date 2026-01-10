#!/usr/bin/env bash
set -e

exec gunicorn phishing_awareness_flask_render.app:app \
  --bind 0.0.0.0:${PORT} \
  --workers ${WEB_CONCURRENCY:-1} \
  --timeout 120
