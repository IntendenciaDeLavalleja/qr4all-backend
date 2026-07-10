#!/bin/sh
# QR4All Lavalleja backend entrypoint

set -e

echo "Setting up Prometheus multiprocess directory at $PROMETHEUS_MULTIPROC_DIR"
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

echo "Running database migrations..."
if ! flask db upgrade; then
    echo "WARNING: Database migration failed. The application will still start but may not function correctly."
fi

echo "Starting Gunicorn..."
exec gunicorn -c /app/gunicorn.conf.py "wsgi:app"