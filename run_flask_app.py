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
from app import app, start_backend, stop_backend

def main():
    """Main entry point for Flask application"""
    print("Starting CORE Scout Flask Application...")
    
    # Start the backend
    print("Starting backend service...")
    if not start_backend():
        print("Warning: Backend failed to start. Some features may not work.")
    
    try:
        # Enable debug for auto-reload of templates and static files
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        try:
            app.jinja_env.auto_reload = True
        except Exception:
            pass

        # Run Flask app
        print("Starting Flask frontend on http://127.0.0.1:5000")
        app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_backend()
        print("Application stopped.")

if __name__ == '__main__':
    main()
