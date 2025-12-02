"""
Flask frontend for CORE-Scout application
Converted from Node.js/React to Flask for deployment compatibility
"""

import os
import json
import requests
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import tempfile
import subprocess
import signal
import sys
from core.utilities.logging_config import get_logger

# Set up logging
logger = get_logger('flask_app')

app = Flask(__name__)
# Ensure templates and static assets refresh during development and when using the run script
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
try:
    # Some environments require explicitly toggling the Jinja env
    app.jinja_env.auto_reload = True
except Exception:
    pass
app.secret_key = 'core-scout-secret-key-2024'

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"
BACKEND_PROCESS = None
BACKEND_PORT = 8000
CURRENT_DB_FILE = None

def start_backend():
    """
    Start the FastAPI backend
    Uses thread-based approach for Posit Connect compatibility
    Falls back to subprocess for local development if needed
    """
    global BACKEND_PROCESS
    
    # Check if we're in Posit Connect environment
    # Posit Connect sets specific environment variables
    is_posit_connect = os.getenv('RSTUDIO_PRODUCT') == 'CONNECT' or os.getenv('RS_CONNECT_SERVER') is not None
    
    if is_posit_connect:
        # Use thread-based backend for Posit Connect
        logger.info("Detected Posit Connect environment, using thread-based backend")
        from core.utilities.backend_runner import start_backend_in_thread
        return start_backend_in_thread(port=BACKEND_PORT)
    else:
        # Use subprocess for local development
        logger.info("Local development environment, using subprocess backend")
        if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
            logger.info("Backend process already running")
            return True  # Backend already running
        
        try:
            logger.info("Starting FastAPI backend on port %s", BACKEND_PORT)
            # Clear any database environment variables to ensure clean startup
            env = os.environ.copy()
            env.pop('DB_PATH', None)
            env.pop('API_PORT', None)
            
            # Start the backend process without any database
            cmd = [sys.executable, "run_app_dynamic.py", "--port", str(BACKEND_PORT)]
            # IMPORTANT: Do not PIPE stdout/stderr without consuming them; buffers can fill and block the child process.
            # Redirect to DEVNULL to avoid hangs caused by heavy backend logging during long operations.
            BACKEND_PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            logger.info("Backend process started with PID %s", BACKEND_PROCESS.pid)
            
            # Wait for backend to be ready
            for _ in range(20):  # 10 seconds timeout
                try:
                    response = requests.get(f"{API_BASE_URL}/health", timeout=1)
                    if response.status_code == 200:
                        logger.info("Backend started successfully on port %s", BACKEND_PORT)
                        return True
                except requests.exceptions.RequestException:
                    time.sleep(0.5)
            
            logger.error("Backend failed to start within timeout")
            return False
        except Exception as e:
            logger.error("Error starting backend: %s", e, exc_info=True)
            return False

def stop_backend():
    """Stop the FastAPI backend (process or thread)"""
    global BACKEND_PROCESS
    
    # Check if we're using thread-based backend
    is_posit_connect = os.getenv('RSTUDIO_PRODUCT') == 'CONNECT' or os.getenv('RS_CONNECT_SERVER') is not None
    
    if is_posit_connect:
        from core.utilities.backend_runner import stop_backend_thread
        stop_backend_thread()
    else:
        # Stop subprocess backend
        if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
            logger.info("Stopping backend process")
            try:
                BACKEND_PROCESS.terminate()
                BACKEND_PROCESS.wait(timeout=5)
                logger.info("Backend process terminated successfully")
            except subprocess.TimeoutExpired:
                logger.warning("Backend process did not terminate, forcing kill")
                BACKEND_PROCESS.kill()
            BACKEND_PROCESS = None
        else:
            logger.debug("No backend process to stop")

def api_request(method, endpoint, **kwargs):
    """Make API request to backend"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        # Add default timeout if not specified
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
        logger.debug("Making %s request to %s", method, url)
        response = requests.request(method, url, timeout=kwargs.get('timeout', 30), **{k: v for k, v in kwargs.items() if k != 'timeout'})
        logger.debug("Response status: %s", response.status_code)
        return response
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.Timeout) as e:
        logger.warning("API request failed: %s", e)
        return None

@app.route('/')
def home():
    """Home page"""
    logger.debug("Home page requested")
    # Check if backend is running
    health_response = api_request('GET', '/health')
    backend_ready = health_response and health_response.status_code == 200
    logger.debug("Backend ready: %s", backend_ready)
    
    # Don't load database info on startup - start clean
    db_info = None
    
    return render_template('home.html', backend_ready=backend_ready, db_info=db_info, backend_port=BACKEND_PORT)

@app.route('/search')
def search():
    """Search page"""
    logger.debug("Search page requested")
    # Check if backend is running
    health_response = api_request('GET', '/health')
    if not health_response or health_response.status_code != 200:
        logger.warning("Backend not available for search page")
        flash('Backend not available. Please check settings.', 'error')
        return redirect(url_for('settings'))
    
    # Get tables
    tables_response = api_request('GET', '/tables')
    tables = []
    if tables_response and tables_response.status_code == 200:
        tables = tables_response.json()
    
    # If no tables available, redirect to settings with a helpful message
    if not tables:
        logger.info("No tables detected in database")
        flash('No tables detected in the current database. Please load a valid database in Settings.', 'error')
        return redirect(url_for('settings'))
    
    selected_table = tables[0].get('name', '') if tables else ''
    tables_count = len(tables)
    logger.debug("Search page loaded with %s tables", tables_count)
    return render_template('search.html', tables=tables, selected_table=selected_table)

@app.route('/results')
def search_results():
    """Search results page"""
    query = request.args.get('q', '')
    table = request.args.get('table', '')
    
    logger.info("Search results requested - table: %s, query: %s", table, query)
    

    if not table:
        logger.warning("Search results requested without table")
        flash('Please select a table to search', 'error')
        return redirect(url_for('search'))
    
    # If query is empty, use wildcard to return all results
    if not query:
        query = '*'
    
    # Perform search
    search_params = {
        'q': query,
        'size': 50
    }
    
    search_response = api_request('GET', f'/search/{table}', params=search_params)
    
    if not search_response or search_response.status_code != 200:
        logger.error("Search failed for table %s, query %s", table, query)
        flash('Search failed', 'error')
        return redirect(url_for('search'))
    
    search_data = search_response.json()
    search_hits = search_data.get('hits', [])
    total = search_data.get('total', 0)
    took = search_data.get('took', 0)
    
    logger.info("Search completed - %s results found in %sms", total, took)
    
    # Get table info for MGRS fields
    table_info = None
    table_response = api_request('GET', f'/tables/{table}')
    if table_response and table_response.status_code == 200:
        table_info = table_response.json()
    
    return render_template('results.html', 
                         query=query, 
                         table=table, 
                         results=search_hits, 
                         total=total, 
                         took=took,
                         table_info=table_info)

@app.route('/report/<report_id>')
def report(report_id):
    """Full report page"""
    # Get table name from query parameter (passed from search results)
    table_name = request.args.get('table', '')
    
    if not table_name:
        flash('Table parameter missing', 'error')
        return redirect(url_for('search'))
    
    # Get the record from the backend
    try:
        record_response = api_request('GET', f'/tables/{table_name}/records/{report_id}')
        if not record_response or record_response.status_code != 200:
            flash('Record not found', 'error')
            return redirect(url_for('search'))
        
        record = record_response.json()
        
        # Get table info for schema
        table_info_response = api_request('GET', f'/tables/{table_name}')
        table_info = None
        if table_info_response and table_info_response.status_code == 200:
            table_info = table_info_response.json()
        
        return render_template('report.html', record=record, table_info=table_info, report_id=report_id)
        
    except Exception as e:
        flash(f'Error loading record: {str(e)}', 'error')
        return redirect(url_for('search'))

@app.route('/create')
def create():
    """Database creation page"""
    # Get supported formats
    formats_response = api_request('GET', '/supported-formats')
    supported_formats = []
    if formats_response and formats_response.status_code == 200:
        supported_formats = formats_response.json()
    
    return render_template('create.html', supported_formats=supported_formats)

@app.route('/create_database', methods=['POST'])
def create_database():
    """Handle database creation (legacy route)"""
    folder_path = request.form.get('folder_path')
    db_name = request.form.get('db_name')
    
    if not folder_path or not db_name:
        flash('Missing required fields', 'error')
        return redirect(url_for('create'))
    
    # Prepare options
    options = {
        'extractText': request.form.get('extract_text') == 'on',
        'extractCoordinates': request.form.get('extract_coordinates') == 'on',
        'includeImages': request.form.get('include_images') == 'on',
        'recursive': request.form.get('recursive') == 'on',
        'fileTypes': request.form.getlist('file_types')
    }
    
    # Create database via API
    create_data = {
        'folderPath': folder_path,
        'dbName': db_name,
        'options': json.dumps(options)
    }
    
    response = api_request('POST', '/create-database', json=create_data)
    
    if response and response.status_code == 200:
        result = response.json()
        if result.get('success'):
            flash(f'Database created successfully: {result.get("message", "")}', 'success')
            # Switch to new database
            switch_data = {'dbPath': result.get('dbPath')}
            switch_response = api_request('POST', '/switch-database', json=switch_data)
            if switch_response and switch_response.status_code == 200:
                flash('Switched to new database', 'info')
        else:
            flash(f'Database creation failed: {result.get("error", "Unknown error")}', 'error')
    else:
        flash('Database creation failed', 'error')
    
    return redirect(url_for('create'))

@app.route('/test_upload', methods=['POST'])
def test_upload():
    """Test route to verify upload handling works"""
    try:
        logger.debug("Received test upload request")
        form_keys = list(request.form.keys())
        files_count = len(request.files.getlist('files'))
        logger.debug("Form data keys: %s", form_keys)
        logger.debug("Files received: %s", files_count)
        return jsonify({'success': True, 'message': 'Test upload successful'})
    except Exception as e:
        logger.error("Test upload error: %s", str(e), exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/select_folder', methods=['POST'])
def select_folder():
    """Open native folder dialog and return the selected folder path"""
    try:
        # Run a small inline Python script to open the folder picker.
        # This avoids writing files inside the project directory, which was triggering the Flask reloader.
        inline_code = (
            "import tkinter as tk\n"
            "from tkinter import filedialog\n"
            "try:\n"
            "    root = tk.Tk()\n"
            "    root.withdraw()\n"
            "    p = filedialog.askdirectory(title='Select folder to process')\n"
            "    root.destroy()\n"
            "    print(p if p else 'NO_FOLDER_SELECTED')\n"
            "except Exception as e:\n"
            "    print('ERROR: ' + str(e))\n"
        )

        try:
            result = subprocess.run(
                [sys.executable, "-c", inline_code],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output == "NO_FOLDER_SELECTED":
                    return jsonify({'success': False, 'error': 'No folder selected'})
                if output.startswith("ERROR:"):
                    return jsonify({'success': False, 'error': output[6:]})
                return jsonify({'success': True, 'folder_path': output})

            return jsonify({'success': False, 'error': f'Script failed: {result.stderr}'})

        except subprocess.TimeoutExpired:
            return jsonify({'success': False, 'error': 'Folder selection timed out'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
            
    except Exception as e:
        logger.error("Error in select_folder: %s", str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/create_database_from_folder', methods=['POST'])
def create_database_from_folder():
    """Handle database creation from uploaded folder"""
    try:
        logger.info("Received folder upload request")
        form_keys = list(request.form.keys())
        files_count = len(request.files.getlist('files'))
        logger.debug("Form data keys: %s", form_keys)
        logger.debug("Files received: %s", files_count)
        
        # Get form data
        db_name = request.form.get('db_name')
        logger.info("Database name: %s", db_name)
        if not db_name:
            logger.warning("Database name missing in request")
            return jsonify({'success': False, 'error': 'Database name is required'}), 400
        
        # Get processing options
        extract_text = request.form.get('extract_text') == 'true'
        extract_coordinates = request.form.get('extract_coordinates') == 'true'
        include_images = request.form.get('include_images') == 'true'
        recursive = request.form.get('recursive') == 'true'
        file_types = request.form.getlist('file_types')
        
        # Get folder path from form data
        folder_path = request.form.get('folder_path')
        logger.info("Folder path: %s", folder_path)
        if not folder_path:
            logger.warning("Folder path missing in request")
            return jsonify({'success': False, 'error': 'Folder path is required'}), 400
        
        # Verify folder exists
        if not os.path.exists(folder_path):
            logger.error("Folder does not exist: %s", folder_path)
            return jsonify({'success': False, 'error': f'Folder does not exist: {folder_path}'}), 400
        
        # Prepare options for backend
        options = {
            'extractText': extract_text,
            'extractCoordinates': extract_coordinates,
            'includeImages': include_images,
            'recursive': recursive,
            'fileTypes': file_types
        }
        
        # Create database via backend API using the original folder path
        create_data = {
            'folderPath': folder_path,
            'dbName': db_name,
            'options': json.dumps(options)
        }
        
        logger.info("Calling backend API with folder_path: %s", folder_path)
        logger.debug("Create data: %s", create_data)
        
        # Check if backend is running first
        logger.debug("Checking backend health...")
        health_response = api_request('GET', '/health', timeout=5)
        if not health_response:
            logger.error("Backend health check failed")
            return jsonify({'success': False, 'error': 'Backend is not responding'}), 500
        
        logger.info("Backend health check passed, calling create-database...")
        response = api_request('POST', '/create-database', json=create_data, timeout=300)  # 5 minute timeout
        response_status = response.status_code if response else 'None'
        logger.info("Backend response: %s", response_status)
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get('success'):
                db_path = result.get('dbPath')
                logger.info("Database created successfully: %s", db_path)
                
                # Switch to the new database
                switch_data = {'dbPath': db_path}
                api_request('POST', '/switch-database', json=switch_data)
                
                return jsonify({
                    'success': True,
                    'message': f'Database created successfully: {result.get("message", "")}',
                    'dbPath': db_path
                })
            else:
                logger.error("Database creation failed: %s", result.get('error', 'Unknown error'))
                return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500
        else:
            logger.error("Backend API call failed")
            return jsonify({'success': False, 'error': 'Backend API call failed'}), 500
                
    except Exception as e:
        logger.error("Error in create_database_from_folder: %s", str(e), exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')

@app.route('/upload_database', methods=['POST'])
def upload_database():
    """Handle database upload"""
    global CURRENT_DB_FILE
    
    logger.info("Database upload requested")
    
    if 'database_file' not in request.files:
        logger.warning("Database upload attempted without file")
        flash('No file selected', 'error')
        return redirect(url_for('settings'))
    
    file = request.files['database_file']
    if file.filename == '':
        logger.warning("Database upload attempted with empty filename")
        flash('No file selected', 'error')
        return redirect(url_for('settings'))
    
    if file and file.filename.lower().endswith(('.db', '.sqlite', '.sqlite3')):
        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save new file
        filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(uploads_dir, unique_filename)
        file.save(file_path)
        
        logger.info("Database file saved: %s", file_path)
        
        # Switch to uploaded database
        switch_data = {'dbPath': file_path}
        response = api_request('POST', '/switch-database', json=switch_data)

        # Verify switch succeeded and tables are available
        tables_ok = False
        if response and response.status_code == 200:
            tables_resp = api_request('GET', '/tables')
            if tables_resp and tables_resp.status_code == 200:
                try:
                    tables_list = tables_resp.json() or []
                    tables_ok = isinstance(tables_list, list) and len(tables_list) > 0
                    tables_count = len(tables_list)
                    logger.info("Database loaded with %s tables", tables_count)
                except Exception as e:
                    logger.error("Error parsing tables response: %s", e)
                    tables_ok = False

        if response and response.status_code == 200 and tables_ok:
            # Clean up previous database file
            if CURRENT_DB_FILE and os.path.exists(CURRENT_DB_FILE):
                try:
                    os.remove(CURRENT_DB_FILE)
                    logger.debug("Removed previous database file: %s", CURRENT_DB_FILE)
                except OSError as e:
                    logger.warning("Failed to remove previous database file: %s", e)

            # Update current database file
            CURRENT_DB_FILE = file_path
            logger.info("Database successfully loaded: %s", filename)
            flash(f'Database loaded: {filename}', 'success')
        else:
            logger.error("Failed to load database (no tables detected or switch failed)")
            flash('Failed to load database (no tables detected or switch failed)', 'error')
            # Clean up new file on failure
            try:
                os.remove(file_path)
                logger.debug("Removed failed database file: %s", file_path)
            except OSError as e:
                logger.warning("Failed to remove failed database file: %s", e)
    else:
        logger.warning("Invalid file type uploaded: %s", file.filename)
        flash('Invalid file type. Please upload a .db, .sqlite, or .sqlite3 file', 'error')
    
    return redirect(url_for('settings'))

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')

@app.route('/export_kml/<table_name>')
def export_kml(table_name):
    """Export KML file"""
    query = request.args.get('q', '*')
    mgrs_field = request.args.get('mgrs_field', 'MGRS')
    limit = request.args.get('limit', 10000, type=int)
    
    response = api_request('GET', f'/export/kml/{table_name}', 
                          params={'q': query, 'mgrs_field': mgrs_field, 'limit': limit})
    
    if response and response.status_code == 200:
        # Save response content to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.kml')
        temp_file.write(response.content)
        temp_file.close()
        
        return send_file(temp_file.name, as_attachment=True, 
                        download_name=f'{table_name}.kml',
                        mimetype='application/vnd.google-earth.kml+xml')
    else:
        flash('KML export failed', 'error')
        return redirect(url_for('results'))

@app.route('/api/health')
def api_health():
    """API health check"""
    response = api_request('GET', '/health')
    if response and response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({'status': 'unhealthy', 'database_connected': False}), 503

@app.route('/api/tables')
def api_tables():
    """API endpoint for tables"""
    response = api_request('GET', '/tables')
    if response and response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify([])

@app.route('/api/search/<table_name>')
def api_search(table_name):
    """API endpoint for search"""
    query = request.args.get('q', '*')
    size = request.args.get('size', 50, type=int)
    
    response = api_request('GET', f'/search/{table_name}', 
                          params={'q': query, 'size': size})
    
    if response and response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({'error': 'Search failed'}), 500

@app.route('/api/switch-database', methods=['POST'])
def api_switch_database():
    """API endpoint for switching database"""
    data = request.get_json()
    db_path = data.get('dbPath') if data else None
    
    if not db_path or not os.path.exists(db_path):
        return jsonify({'error': 'Database file not found'}), 404
    
    # Switch the database via backend API
    switch_data = {'dbPath': db_path}
    response = api_request('POST', '/switch-database', json=switch_data)
    
    if response and response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({'error': 'Failed to switch database'}), 500

# Startup and shutdown handlers
# Backend initialization is handled by app_wsgi.py for Posit Connect
# For local development, backend starts in __main__ block below

def signal_handler(signum, frame):  # pylint: disable=unused-argument
    """Handle shutdown signals"""
    logger.info("Shutdown signal received")
    stop_backend()
    sys.exit(0)

if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start backend
    if not start_backend():
        logger.warning("Backend failed to start")
    
    try:
        app.run(debug=True, host='127.0.0.1', port=5000)
    finally:
        stop_backend()
