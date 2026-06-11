#!/usr/bin/env python3
"""AI Email Reading Agent — entry point.

Starts the Flask web server (dashboard) and the background scheduler thread.
"""

from __future__ import annotations

import logging
import threading

from flask import Flask

from config import load_config
from app.dashboard.routes import dashboard_bp
from app.models.database import init_db
from app.scheduler import run_poll_loop

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Enable DEBUG logging for the API classifier so LLM input/output is visible
logging.getLogger("app.classifier.api").setLevel(logging.DEBUG)
# Also enable for the scheduler to see classification decisions
logging.getLogger("app.scheduler").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    """Create and configure the Flask application."""
    cfg = load_config(env_file=".env")

    app = Flask(__name__)
    app.config["DATABASE_PATH"] = cfg.database_path
    app.config["DEBUG"] = cfg.debug

    # Initialise the database (creates tables on first run)
    init_db(cfg.database_path_resolved)

    # Register dashboard blueprint
    app.register_blueprint(dashboard_bp)

    return app


import signal
import sys

from app.models.database import close_connection


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


def _shutdown(signum: int, frame: object | None) -> None:
    """Clean up resources before exiting."""
    logger.info("Shutdown signal received — cleaning up...")
    close_connection()
    logger.info("Database connection closed. Exiting.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    cfg = load_config(env_file=".env")
    app = create_app()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start the background scheduler in a daemon thread
    scheduler_thread = threading.Thread(
        target=run_poll_loop,
        args=(cfg.database_path, cfg.poll_interval),
        daemon=True,
        name="email-scheduler",
    )
    scheduler_thread.start()
    logger.info("Background scheduler thread started")

    # Run Flask (blocking)
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=cfg.debug,
        use_reloader=False,  # avoid double scheduler with reloader
    )

if __name__ == "__main__":
    main()
