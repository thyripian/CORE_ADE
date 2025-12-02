"""
Backend runner for Posit Connect compatibility
Runs FastAPI backend in a thread instead of a subprocess
This avoids subprocess restrictions in containerized environments
"""

import threading
import time
import requests
from core.utilities.logging_config import get_logger

logger = get_logger('backend_runner')

# Global variables to track backend state
_backend_thread = None
_backend_app = None
_backend_server = None
_backend_port = None
_backend_ready = False
_backend_lock = threading.Lock()

def start_backend_in_thread(port=8000):
    """
    Start FastAPI backend in a background thread (Posit Connect compatible)
    This avoids subprocess spawning which may be restricted in Posit Connect
    
    Args:
        port: Port to run the backend on (default: 8000)
    
    Returns:
        True if backend started successfully, False otherwise
    """
    global _backend_thread, _backend_app, _backend_server, _backend_port, _backend_ready
    
    with _backend_lock:
        if _backend_thread and _backend_thread.is_alive():
            logger.info("Backend thread already running")
            return True
        
        try:
            logger.info("Starting FastAPI backend in thread on port %s", port)
            
            # Import here to avoid circular imports
            try:
                import uvicorn
            except ImportError:
                logger.error("uvicorn not installed. Please install it: pip install uvicorn")
                return False
            
            from run_app_dynamic import create_fastapi_app
            
            # Create FastAPI app instance
            _backend_app = create_fastapi_app()
            _backend_port = port
            
            # Create uvicorn server config
            # Use asyncio loop for compatibility
            config = uvicorn.Config(
                app=_backend_app,
                host="127.0.0.1",
                port=port,
                log_level="info",
                access_log=False,  # Reduce logging noise
                loop="asyncio",
                use_colors=False  # Disable colors for Posit Connect
            )
            
            _backend_server = uvicorn.Server(config)
            
            # Start backend in a daemon thread
            def run_backend():
                global _backend_ready
                try:
                    logger.info("Backend thread starting, will serve on 127.0.0.1:%s", port)
                    # Mark as ready before starting (server will handle errors)
                    _backend_ready = True
                    _backend_server.run()
                except Exception as e:
                    logger.error("Backend thread error: %s", e, exc_info=True)
                    _backend_ready = False
            
            _backend_thread = threading.Thread(target=run_backend, daemon=True, name="FastAPI-Backend")
            _backend_thread.start()
            
            # Wait for the server to actually start and respond
            logger.info("Waiting for backend to be ready...")
            for attempt in range(30):  # 15 seconds timeout (longer for Posit Connect)
                try:
                    # Give the server a moment to start
                    time.sleep(0.5)
                    
                    # Try to connect to health endpoint
                    response = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
                    if response.status_code == 200:
                        logger.info("Backend started successfully on port %s", port)
                        return True
                except (requests.exceptions.ConnectionError, requests.exceptions.RequestException):
                    # Server not ready yet, continue waiting
                    if attempt % 5 == 0:  # Log every 2.5 seconds
                        attempt_num = attempt + 1
                        logger.debug("Waiting for backend... (attempt %s/30)", attempt_num)
                    continue
                except Exception as e:
                    logger.warning("Error checking backend health: %s", e)
            
            # If we get here, backend didn't start
            logger.error("Backend failed to start within timeout")
            _backend_ready = False
            return False
            
        except Exception as e:
            logger.error("Error starting backend thread: %s", e, exc_info=True)
            _backend_ready = False
            return False

def stop_backend_thread():
    """Stop the FastAPI backend thread"""
    global _backend_thread, _backend_server, _backend_ready
    
    with _backend_lock:
        if _backend_server:
            try:
                logger.info("Stopping backend server")
                _backend_server.should_exit = True
                # Give it a moment to shut down gracefully
                time.sleep(1)
            except Exception as e:
                logger.error("Error stopping backend server: %s", e, exc_info=True)
        
        _backend_ready = False
        _backend_thread = None
        _backend_server = None
        _backend_app = None

def is_backend_ready():
    """Check if backend is ready"""
    return _backend_ready and _backend_thread and _backend_thread.is_alive()

