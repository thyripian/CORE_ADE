"""
WSGI entry point for Posit Connect deployment
This file serves as the main application entry point for Posit Connect
"""

import os
import logging
from core.utilities.logging_config import setup_logging

# Set up logging first
logger = setup_logging(
    log_level=os.getenv('LOG_LEVEL', 'INFO'),
    log_file=os.getenv('LOG_FILE', None)
)

logger.info("=" * 60)
logger.info("CORE Scout Application Starting")
logger.info("=" * 60)

# Import Flask app after logging is configured
from app import app

# Configure Flask logging
if not app.debug:
    # In production (Posit Connect), ensure Flask uses our logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)  # Reduce Flask's verbose logging
    
    # Add our handler to werkzeug logger
    for handler in logger.handlers:
        werkzeug_logger.addHandler(handler)

logger.info("Flask application initialized")
logger.info("Application name: %s", app.name)
logger.info("Debug mode: %s", app.debug)

# Initialize backend for Posit Connect
# Use a background thread to start the backend after Flask is ready
def initialize_backend():
    """Initialize backend in background thread for Posit Connect"""
    import threading
    import time
    
    def start_backend_delayed():
        # Wait a moment for Flask to fully initialize
        time.sleep(2)
        logger.info("Initializing backend for Posit Connect...")
        from app import start_backend
        if start_backend():
            logger.info("Backend initialized successfully")
        else:
            logger.warning("Backend initialization failed - some features may not work")
    
    # Start backend in a daemon thread
    backend_thread = threading.Thread(target=start_backend_delayed, daemon=True)
    backend_thread.start()
    logger.info("Backend initialization thread started")

# Initialize backend for Posit Connect
initialize_backend()

# Export WSGI application for Posit Connect
application = app

if __name__ == '__main__':
    # For local development
    logger.info("Running in development mode")
    app.run(debug=True, host='127.0.0.1', port=5000)
else:
    logger.info("Running as WSGI application (Posit Connect)")

