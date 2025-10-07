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
import shutil
import subprocess
import signal
import sys

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
    """Start the FastAPI backend process"""
    global BACKEND_PROCESS
    
    if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
        return True  # Backend already running
    
    try:
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
        
        # Wait for backend to be ready
        for _ in range(20):  # 10 seconds timeout
            try:
                response = requests.get(f"{API_BASE_URL}/health", timeout=1)
                if response.status_code == 200:
                    print(f"Backend started successfully on port {BACKEND_PORT}")
                    return True
            except requests.exceptions.RequestException:
                time.sleep(0.5)
        
        print("Backend failed to start within timeout")
        return False
    except Exception as e:
        print(f"Error starting backend: {e}")
        return False

def stop_backend():
    """Stop the FastAPI backend process"""
    global BACKEND_PROCESS
    
    if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
        try:
            BACKEND_PROCESS.terminate()
            BACKEND_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            BACKEND_PROCESS.kill()
        BACKEND_PROCESS = None

def api_request(method, endpoint, **kwargs):
    """Make API request to backend"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        # Add default timeout if not specified
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
        response = requests.request(method, url, **kwargs)
        return response
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
        return None

@app.route('/')
def home():
    """Home page"""
    # Check if backend is running
    health_response = api_request('GET', '/health')
    backend_ready = health_response and health_response.status_code == 200
    
    # Don't load database info on startup - start clean
    db_info = None
    
    return render_template('home.html', backend_ready=backend_ready, db_info=db_info, backend_port=BACKEND_PORT)

@app.route('/search')
def search():
    """Search page"""
    # Check if backend is running
    health_response = api_request('GET', '/health')
    if not health_response or health_response.status_code != 200:
        flash('Backend not available. Please check settings.', 'error')
        return redirect(url_for('settings'))
    
    # Get tables
    tables_response = api_request('GET', '/tables')
    tables = []
    if tables_response and tables_response.status_code == 200:
        tables = tables_response.json()
    
    selected_table = tables[0].get('name', '') if tables else ''
    return render_template('search.html', tables=tables, selected_table=selected_table)

@app.route('/results')
def search_results():
    """Search results page"""
    query = request.args.get('q', '')
    table = request.args.get('table', '')
    
    if not table:
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
        flash('Search failed', 'error')
        return redirect(url_for('search'))
    
    search_data = search_response.json()
    search_hits = search_data.get('hits', [])
    total = search_data.get('total', 0)
    took = search_data.get('took', 0)
    
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
        print(f"[TEST] Received test upload request")
        print(f"[TEST] Form data keys: {list(request.form.keys())}")
        print(f"[TEST] Files received: {len(request.files.getlist('files'))}")
        return jsonify({'success': True, 'message': 'Test upload successful'})
    except Exception as e:
        print(f"[TEST] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/select_folder', methods=['POST'])
def select_folder():
    """Open native folder dialog and return the selected folder path"""
    try:
        import subprocess
        import sys

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
        print(f"[FLASK] Error in select_folder: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/create_database_from_folder', methods=['POST'])
def create_database_from_folder():
    """Handle database creation from uploaded folder"""
    try:
        print(f"[FLASK] Received folder upload request")
        print(f"[FLASK] Form data keys: {list(request.form.keys())}")
        print(f"[FLASK] Files received: {len(request.files.getlist('files'))}")
        
        # Get form data
        db_name = request.form.get('db_name')
        print(f"[FLASK] Database name: {db_name}")
        if not db_name:
            return jsonify({'success': False, 'error': 'Database name is required'}), 400
        
        # Get processing options
        extract_text = request.form.get('extract_text') == 'true'
        extract_coordinates = request.form.get('extract_coordinates') == 'true'
        include_images = request.form.get('include_images') == 'true'
        recursive = request.form.get('recursive') == 'true'
        file_types = request.form.getlist('file_types')
        
        # Get folder path from form data
        folder_path = request.form.get('folder_path')
        print(f"[FLASK] Folder path: {folder_path}")
        if not folder_path:
            return jsonify({'success': False, 'error': 'Folder path is required'}), 400
        
        # Verify folder exists
        if not os.path.exists(folder_path):
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
        
        print(f"[FLASK] Calling backend API with folder_path: {folder_path}")
        print(f"[FLASK] Create data: {create_data}")
        
        # Check if backend is running first
        print(f"[FLASK] Checking backend health...")
        health_response = api_request('GET', '/health', timeout=5)
        if not health_response:
            print(f"[FLASK] Backend health check failed")
            return jsonify({'success': False, 'error': 'Backend is not responding'}), 500
        
        print(f"[FLASK] Backend health check passed, calling create-database...")
        response = api_request('POST', '/create-database', json=create_data, timeout=300)  # 5 minute timeout
        print(f"[FLASK] Backend response: {response.status_code if response else 'None'}")
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get('success'):
                db_path = result.get('dbPath')
                
                # Switch to the new database
                switch_data = {'dbPath': db_path}
                api_request('POST', '/switch-database', json=switch_data)
                
                return jsonify({
                    'success': True,
                    'message': f'Database created successfully: {result.get("message", "")}',
                    'dbPath': db_path
                })
            else:
                return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500
        else:
            return jsonify({'success': False, 'error': 'Backend API call failed'}), 500
                
    except Exception as e:
        print(f"[FLASK] Error in create_database_from_folder: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')

@app.route('/upload_database', methods=['POST'])
def upload_database():
    """Handle database upload"""
    global CURRENT_DB_FILE
    
    if 'database_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('settings'))
    
    file = request.files['database_file']
    if file.filename == '':
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
        
        # Switch to uploaded database
        switch_data = {'dbPath': file_path}
        response = api_request('POST', '/switch-database', json=switch_data)
        
        if response and response.status_code == 200:
            # Clean up previous database file
            if CURRENT_DB_FILE and os.path.exists(CURRENT_DB_FILE):
                try:
                    os.remove(CURRENT_DB_FILE)
                except OSError:
                    pass
            
            # Update current database file
            CURRENT_DB_FILE = file_path
            flash(f'Database loaded: {filename}', 'success')
        else:
            flash('Failed to load database', 'error')
            # Clean up new file on failure
            try:
                os.remove(file_path)
            except OSError:
                pass
    else:
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
# Remove before_first_request as it's deprecated in newer Flask versions

def signal_handler(signum, frame):  # pylint: disable=unused-argument
    """Handle shutdown signals"""
    stop_backend()
    sys.exit(0)

if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start backend
    if not start_backend():
        print("Warning: Backend failed to start")
    
    try:
        app.run(debug=True, host='127.0.0.1', port=5000)
    finally:
        stop_backend()
