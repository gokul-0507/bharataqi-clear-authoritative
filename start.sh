#!/bin/bash
# start.sh — production startup script (used by Railway / Render)
set -e
echo "Starting CPCB AQI Dashboard on port ${PORT:-8000} ..."
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 2
