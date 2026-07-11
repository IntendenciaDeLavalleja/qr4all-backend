#!/bin/sh
# QR4All Lavalleja backend entrypoint

set -e

echo "QR4ALL ENTRYPOINT STARTED"

if [ "${STARTUP_DIAGNOSTIC_MODE:-false}" = "true" ]; then
    echo "Startup diagnostics enabled"
    id
    pwd
    ls -la /app
    python --version
    command -v flask || true
    command -v gunicorn || true
    for name in DEPLOYMENT_MODE FLASK_APP FLASK_ENV FLASK_DEBUG DATABASE_URL REDIS_URL MINIO_ENDPOINT MINIO_BUCKET_NAME MINIO_PUBLIC_URL FRONTEND_URL PUBLIC_API_BASE_URL CORS_ORIGINS; do
        if printenv "$name" >/dev/null 2>&1; then
            echo "$name=set"
        else
            echo "$name=missing"
        fi
    done
fi

# The image default is under /tmp. Refuse arbitrary paths before removing data.
case "${PROMETHEUS_MULTIPROC_DIR:-}" in
    /tmp/*)
        echo "Setting up Prometheus multiprocess directory at $PROMETHEUS_MULTIPROC_DIR"
        rm -rf -- "$PROMETHEUS_MULTIPROC_DIR"
        mkdir -p -- "$PROMETHEUS_MULTIPROC_DIR"
        ;;
    '')
        echo "PROMETHEUS_MULTIPROC_DIR is not configured; skipping setup."
        ;;
    *)
        echo "PROMETHEUS_MULTIPROC_DIR must be under /tmp; skipping setup."
        ;;
esac

echo "Running database migrations..."
if ! flask db upgrade; then
    echo "WARNING: Database migration failed. The application will still start but may not function correctly."
fi

echo "Starting Gunicorn..."
exec gunicorn -c /app/gunicorn.conf.py "wsgi:app"
