#!/bin/bash
# Railway multi-service startup script
# Routes to the correct process based on RAILWAY_SERVICE_NAME

set -e

if [ "$RAILWAY_SERVICE_NAME" = "celery-worker" ]; then
    echo "Starting Celery worker + beat..."

    # Start the health server as a proper persistent background process.
    # serve_forever() runs on the main thread so the Python process stays alive.
    # The & backgrounds the entire python3 process, not just a daemon thread.
    python3 -c "
import http.server, os, signal, sys

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{\"status\":\"ok\",\"service\":\"celery-worker\"}')
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *args):
        pass

port = int(os.environ.get('PORT', 8080))
server = http.server.HTTPServer(('0.0.0.0', port), HealthHandler)
print(f'Health server listening on port {port}', flush=True)
# Blocks main thread — process stays alive as long as Celery is running.
server.serve_forever()
" &

    exec celery -A app.tasks.celery_app worker --beat --loglevel=info
else
    echo "Starting API server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
fi
