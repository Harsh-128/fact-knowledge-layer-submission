"""
Worker entry point for Render deployment.

Render free Web Services require an open HTTP port. This script starts:
1. A minimal HTTP health server on $PORT (satisfies Render)
2. The Celery worker in a separate thread

Both run together so Render keeps the service alive.
"""
from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from celery import Celery


def run_health_server() -> None:
    """Serve a minimal /health endpoint so Render detects an open port."""

    port = int(os.environ.get("PORT", 8001))

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"worker-ok"}')

        def log_message(self, *args: object) -> None:  # suppress access logs
            pass

    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server listening on port {port}", flush=True)
    server.serve_forever()


def run_celery_worker() -> None:
    """Start the Celery worker in the foreground."""
    from app.workers.celery_app import celery_app  # noqa: PLC0415

    celery_app.worker_main(
        argv=[
            "worker",
            "--loglevel=info",
            "--concurrency=2",
        ]
    )


if __name__ == "__main__":
    # Start the health server in a background daemon thread.
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Run Celery in the main thread (blocking).
    run_celery_worker()
