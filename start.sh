#!/bin/bash
# Railway multi-service startup script
# Routes to the correct process based on RAILWAY_SERVICE_NAME

set -e

if [ "$RAILWAY_SERVICE_NAME" = "celery-worker" ]; then
    echo "Starting Celery worker + beat..."
    exec celery -A app.tasks.celery_app worker --beat --loglevel=info
else
    echo "Starting API server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
fi
