#!/bin/sh
# QR4All Lavalleja backend entrypoint

set -e

# Set up Prometheus multiprocess directory if configured
if [ -n "$PROMETHEUS_MULTIPROC_DIR" ]; then
    echo "Setting up Prometheus multiprocess directory at $PROMETHEUS_MULTIPROC_DIR"
    rm -rf "$PROMETHEUS_MULTIPROC_DIR"
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

echo "Running database migrations..."
flask db upgrade

echo "Starting Gunicorn..."
exec gunicorn -c /app/gunicorn.conf.py "wsgi:app"