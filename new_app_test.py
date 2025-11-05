#!/usr/bin/env python3
"""
CORE Scout - Unified Flask frontend + production runner (ADE/psconnect-ready)

- Starts the FastAPI backend (run_app_dynamic.py) as a child process.
- Waits for backend /health to be ready.
- Serves Flask via Waitress on 0.0.0.0:${PORT} (default 5000).
- Logs to stdout/stderr; clean SIGTERM shutdown.
- Disables GUI folder picker when no display is available.
"""

from __future__ import annotations

import os
import sys
import json
import time
import atexit
import signal
import tempfile
import subprocess
from typing import Optional, Dict, Any

import requests
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    flash, send_file
)
from werkzeug.utils import secure_filename

# -----------------------------
# Config / environment
# -----------------------------

# Frontend (Flask) listen host/port — psconnect typically supplies PORT.
FLASK_HOST = os.getenv("HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("PORT", "5000"))

# Backend (FastAPI) target
API_HOST = os.getenv("CORE_API_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("CORE_API_PORT", "8000"))
API_BASE_URL = f"http://{API_HOST}:{BACKEND_PORT}"

# Secret key (set a strong one in production)
SECRET_KEY = os.getenv("CORE_SCOUT_SECRET_KEY", "core-scout-secret-key-2024")

# Allow disabling the child backend if infra runs it separately
DISABLE_EMBEDDED_BACKEND = os.getenv("DISABLE_EMBEDDED_BACKEND", "0") in {"1", "true", "True"}

# Headless environment (ADE likely true) — disables Tk dialogs
HEADLESS = os.getenv("HEADLESS", "1") in {"1", "true", "True"}

# -----------------------------
# Flask app
# -----------------------------

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Production: still nice to auto-reload templates when packaging updates, but harmless if off.
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
try:
    app.jinja_env.auto_reload = True
except Exception:
    pass

# -----------------------------
# Backend process management
# -----------------------------

BACKEND_PROCESS: Optional[subprocess.Popen] = None
CURRENT_DB_FILE: Optional[str] = None


def _creationflags_no_window() -> int:
    """Windows-friendly creation flags to avoid console window."""
    if os.name == 'nt' and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return 0


def start_backend() -> bool:
    """
    Start the FastAPI backend (run_app_dynamic.py) unless disabled or already running.
    Avoids piping stdout/stderr (to prevent deadlocks). Writes logs to parent stdout by default.
    """
    global BACKEND_PROCESS

    if DISABLE_EMBEDDED_BACKEND:
        print("[CORE] Embedded backend startup disabled via DISABLE_EMBEDDED_BACKEND=1")
        return True

    if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
        print("[CORE] Backend already running")
        return True

    try:
        env = os.environ.copy()
        # Clear conflicting vars; backend will choose DB/port at runtime or via its own env
        env.pop('DB_PATH', None)
        env.pop('API_PORT', None)

        cmd = [sys.executable, "run_app_dynamic.py", "--port", str(BACKEND_PORT)]
        # Log to parent stdout/stderr (psconnect captures these)
        BACKEND_PROCESS = subprocess.Popen(
            cmd,
            env=env,
            creationflags=_creationflags_no_window()
        )

        # Wait for backend /health
        for _ in range(40):  # ~20 seconds
            try:
                r = requests.get(f"{API_BASE_URL}/health", timeout=1.5)
                if r.status_code == 200:
                    print(f"[CORE] Backend ready at {API_BASE_URL}")
                    return True
            except requests.exceptions.RequestException:
                time.sleep(0.5)

        print("[CORE] Backend failed to become ready within timeout")
        return False

    except Exception as e:
        print(f"[CORE] Error starting backend: {e}")
        return False


def stop_backend() -> None:
    """Terminate the FastAPI backend process if running."""
    global BACKEND_PROCESS
    if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
        try:
            BACKEND_PROCESS.terminate()
            BACKEND_PROCESS.wait(timeout=8)
        except subprocess.TimeoutExpired:
            BACKEND_PROCESS.kill()
        finally:
            BACKEND_PROCESS = None


# Ensure child is killed if the parent exits unexpectedly
atexit.register(stop_backend)


# -----------------------------
# Backend HTTP helper
# -----------------------------

def api_request(method: str, endpoint: str, **kwargs):
    """Requests wrapper to backend. Returns requests.Response or None on connection/timeouts."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
        return requests.request(method, url, **kwargs)
    except (requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout):
        return None


# -----------------------------
# Routes: UI
# -----------------------------

@app.route('/')
def home():
    health_response = api_request('GET', '/health')
    backend_ready = bool(health_response and health_response.status_code == 200)
    return render_template('home.html', backend_ready=backend_ready, db_info=None, backend_port=BACKEND_PORT)


@app.route('/search')
def search():
    health_response = api_request('GET', '/health')
    if not health_response or health_response.status_code != 200:
        flash('Backend not available. Please check settings.', 'error')
        return redirect(url_for('settings'))

    tables_response = api_request('GET', '/tables')
    tables = tables_response.json() if (tables_response and tables_response.status_code == 200) else []

    if not tables:
        flash('No tables detected in the current database. Please load a valid database in Settings.', 'error')
        return redirect(url_for('settings'))

    selected_table = tables[0].get('name', '') if tables else ''
    return render_template('search.html', tables=tables, selected_table=selected_table)


@app.route('/results')
def search_results():
    query = request.args.get('q', '') or '*'
    table = request.args.get('table', '')
    if not table:
        flash('Please select a table to search', 'error')
        return redirect(url_for('search'))

    resp = api_request('GET', f'/search/{table}', params={'q': query, 'size': 50})
    if not resp or resp.status_code != 200:
        flash('Search failed', 'error')
        return redirect(url_for('search'))

    data = resp.json()
    hits = data.get('hits', [])
    total = data.get('total', 0)
    took = data.get('took', 0)

    table_info = None
    tinfo = api_request('GET', f'/tables/{table}')
    if tinfo and tinfo.status_code == 200:
        table_info = tinfo.json()

    return render_template('results.html',
                           query=query, table=table,
                           results=hits, total=total, took=took,
                           table_info=table_info)


@app.route('/report/<report_id>')
def report(report_id):
    table_name = request.args.get('table', '')
    if not table_name:
        flash('Table parameter missing', 'error')
        return redirect(url_for('search'))

    try:
        rr = api_request('GET', f'/tables/{table_name}/records/{report_id}')
        if not rr or rr.status_code != 200:
            flash('Record not found', 'error')
            return redirect(url_for('search'))

        record = rr.json()
        table_info = None
        tinfo = api_request('GET', f'/tables/{table_name}')
        if tinfo and tinfo.status_code == 200:
            table_info = tinfo.json()

        return render_template('report.html', record=record, table_info=table_info, report_id=report_id)

    except Exception as e:
        flash(f'Error loading record: {str(e)}', 'error')
        return redirect(url_for('search'))


@app.route('/create')
def create():
    resp = api_request('GET', '/supported-formats')
    supported_formats = resp.json() if (resp and resp.status_code == 200) else []
    return render_template('create.html', supported_formats=supported_formats)


@app.route('/settings')
def settings():
    return render_template('settings.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


# -----------------------------
# Routes: Operations
# -----------------------------

@app.route('/create_database', methods=['POST'])
def create_database():
    folder_path = request.form.get('folder_path')
    db_name = request.form.get('db_name')

    if not folder_path or not db_name:
        flash('Missing required fields', 'error')
        return redirect(url_for('create'))

    options = {
        'extractText': request.form.get('extract_text') == 'on',
        'extractCoordinates': request.form.get('extract_coordinates') == 'on',
        'includeImages': request.form.get('include_images') == 'on',
        'recursive': request.form.get('recursive') == 'on',
        'fileTypes': request.form.getlist('file_types')
    }

    create_data = {'folderPath': folder_path, 'dbName': db_name, 'options': json.dumps(options)}
    resp = api_request('POST', '/create-database', json=create_data)

    if resp and resp.status_code == 200:
        result = resp.json()
        if result.get('success'):
            flash(f'Database created successfully: {result.get("message", "")}', 'success')
            switch_resp = api_request('POST', '/switch-database', json={'dbPath': result.get('dbPath')})
            if switch_resp and switch_resp.status_code == 200:
                flash('Switched to new database', 'info')
        else:
            flash(f'Database creation failed: {result.get("error", "Unknown error")}', 'error')
    else:
        flash('Database creation failed', 'error')

    return redirect(url_for('create'))


@app.route('/test_upload', methods=['POST'])
def test_upload():
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
    """Open native folder dialog; disabled in headless/ADE."""
    if HEADLESS:
        return jsonify({'success': False, 'error': 'Folder selection not available in headless environment'}), 400

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
            creationflags=_creationflags_no_window()
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


@app.route('/create_database_from_folder', methods=['POST'])
def create_database_from_folder():
    try:
        db_name = request.form.get('db_name')
        if not db_name:
            return jsonify({'success': False, 'error': 'Database name is required'}), 400

        extract_text = request.form.get('extract_text') == 'true'
        extract_coordinates = request.form.get('extract_coordinates') == 'true'
        include_images = request.form.get('include_images') == 'true'
        recursive = request.form.get('recursive') == 'true'
        file_types = request.form.getlist('file_types')

        folder_path = request.form.get('folder_path')
        if not folder_path:
            return jsonify({'success': False, 'error': 'Folder path is required'}), 400
        if not os.path.exists(folder_path):
            return jsonify({'success': False, 'error': f'Folder does not exist: {folder_path}'}), 400

        options = {
            'extractText': extract_text,
            'extractCoordinates': extract_coordinates,
            'includeImages': include_images,
            'recursive': recursive,
            'fileTypes': file_types
        }
        payload = {'folderPath': folder_path, 'dbName': db_name, 'options': json.dumps(options)}

        # Check backend then create
        if not api_request('GET', '/health', timeout=5):
            return jsonify({'success': False, 'error': 'Backend is not responding'}), 500

        resp = api_request('POST', '/create-database', json=payload, timeout=300)
        if resp and resp.status_code == 200:
            result = resp.json()
            if result.get('success'):
                db_path = result.get('dbPath')
                api_request('POST', '/switch-database', json={'dbPath': db_path})
                return jsonify({'success': True, 'message': result.get('message', ''), 'dbPath': db_path})
            return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500

        return jsonify({'success': False, 'error': 'Backend API call failed'}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload_database', methods=['POST'])
def upload_database():
    global CURRENT_DB_FILE

    if 'database_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('settings'))
    file = request.files['database_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('settings'))

    if file and file.filename.lower().endswith(('.db', '.sqlite', '.sqlite3')):
        uploads_dir = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)

        filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(uploads_dir, unique_filename)
        file.save(file_path)

        resp = api_request('POST', '/switch-database', json={'dbPath': file_path})

        tables_ok = False
        if resp and resp.status_code == 200:
            tables_resp = api_request('GET', '/tables')
            if tables_resp and tables_resp.status_code == 200:
                try:
                    tables_list = tables_resp.json() or []
                    tables_ok = isinstance(tables_list, list) and len(tables_list) > 0
                except Exception:
                    tables_ok = False

        if resp and resp.status_code == 200 and tables_ok:
            if CURRENT_DB_FILE and os.path.exists(CURRENT_DB_FILE):
                try:
                    os.remove(CURRENT_DB_FILE)
                except OSError:
                    pass
            CURRENT_DB_FILE = file_path
            flash(f'Database loaded: {filename}', 'success')
        else:
            flash('Failed to load database (no tables detected or switch failed)', 'error')
            try:
                os.remove(file_path)
            except OSError:
                pass
    else:
        flash('Invalid file type. Please upload a .db, .sqlite, or .sqlite3 file', 'error')

    return redirect(url_for('settings'))


@app.route('/export_kml/<table_name>')
def export_kml(table_name):
    query = request.args.get('q', '*')
    mgrs_field = request.args.get('mgrs_field', 'MGRS')
    limit = request.args.get('limit', 10000, type=int)

    resp = api_request(
        'GET',
        f'/export/kml/{table_name}',
        params={'q': query, 'mgrs_field': mgrs_field, 'limit': limit}
    )
    if resp and resp.status_code == 200:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.kml')
        tmp.write(resp.content)
        tmp.close()
        return send_file(
            tmp.name,
            as_attachment=True,
            download_name=f'{table_name}.kml',
            mimetype='application/vnd.google-earth.kml+xml'
        )

    flash('KML export failed', 'error')
    return redirect(url_for('results'))


# -----------------------------
# Thin API proxies for frontend
# -----------------------------

@app.route('/api/health')
def api_health():
    """Flask-level health that reflects backend status (good for psconnect probes)."""
    backend = api_request('GET', '/health')
    if backend and backend.status_code == 200:
        return jsonify({'status': 'ok', 'backend': 'ok'}), 200
    return jsonify({'status': 'degraded', 'backend': 'down'}), 503


@app.route('/api/tables')
def api_tables():
    resp = api_request('GET', '/tables')
    if resp and resp.status_code == 200:
        return jsonify(resp.json())
    return jsonify([])


@app.route('/api/search/<table_name>')
def api_search(table_name):
    query = request.args.get('q', '*')
    size = request.args.get('size', 50, type=int)
    resp = api_request('GET', f'/search/{table_name}', params={'q': query, 'size': size})
    if resp and resp.status_code == 200:
        return jsonify(resp.json())
    return jsonify({'error': 'Search failed'}), 500


@app.route('/api/switch-database', methods=['POST'])
def api_switch_database():
    data = request.get_json()
    db_path = data.get('dbPath') if data else None
    if not db_path or not os.path.exists(db_path):
        return jsonify({'error': 'Database file not found'}), 404
    resp = api_request('POST', '/switch-database', json={'dbPath': db_path})
    if resp and resp.status_code == 200:
        return jsonify(resp.json())
    return jsonify({'error': 'Failed to switch database'}), 500


# -----------------------------
# Signal handling / entrypoint
# -----------------------------

def _signal_handler(signum, frame):  # noqa: ARG001
    stop_backend()
    # Let waitress exit cleanly after child stops
    os._exit(0)  # ensures psconnect sees immediate container stop


def main():
    """Main entry: start backend (unless disabled) and serve Flask via Waitress."""
    # Install signal handlers for clean shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if not start_backend():
        print("[CORE] Warning: Backend failed to start. Some features may not work.")

    print(f"[CORE] Starting Flask via Waitress on {FLASK_HOST}:{FLASK_PORT}")
    try:
        from waitress import serve
    except ImportError:
        # Fallback: Flask dev server (still binds correctly for psconnect)
        print("[CORE] WARNING: waitress not installed; falling back to Flask dev server")
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)
        return

    # Production WSGI server
    serve(app, host=FLASK_HOST, port=FLASK_PORT)


if __name__ == '__main__':
    main()
