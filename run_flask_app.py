#!/usr/bin/env python3
"""
Run script for CORE Scout Flask application
"""

import os
import sys
import subprocess
import time
import signal
import threading
from core.utilities.logging_config import setup_logging, get_logger
from app import app, start_backend, stop_backend

# Set up logging
logger = setup_logging(
    log_level=os.getenv('LOG_LEVEL', 'INFO'),
    log_file=os.getenv('LOG_FILE', None)
)

def main():
    """Main entry point for Flask application"""
    logger.info("=" * 60)
    logger.info("Starting CORE Scout Flask Application...")
    logger.info("=" * 60)
    
    # Start the backend
    logger.info("Starting backend service...")
    if not start_backend():
        logger.warning("Backend failed to start. Some features may not work.")
    
    try:
        # Enable debug for auto-reload of templates and static files
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        try:
            app.jinja_env.auto_reload = True
        except Exception:
            pass

        # Run Flask app
        logger.info("Starting Flask frontend on http://127.0.0.1:5000")
        app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        stop_backend()
        logger.info("Application stopped.")

if __name__ == '__main__':
    main()
