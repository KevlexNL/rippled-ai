#!/bin/bash
# Railway multi-service startup script
# Routes to the correct process based on RAILWAY_SERVICE_NAME

set -e

if [ "$RAILWAY_SERVICE_NAME" = "celery-worker" ]; then
    echo "Starting Celery worker + beat..."

    # Start a minimal health HTTP server in the background.
    # Always returns 200 immediately — the process being alive is sufficient for Railway.
    python3 -c "
import http.server, threading, os

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
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()
print(f'Health server listening on port {port}')
" &

    exec celery -A app.tasks.celery_app worker --beat --loglevel=info
else
    echo "Starting API server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
fi
