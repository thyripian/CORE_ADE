# CORE Scout - Flask Version

This is the Flask-based frontend for CORE Scout, converted from the original Node.js/React version for deployment compatibility.

## Features

- **Database Search**: Search through SQLite databases with full-text search capabilities
- **Database Creation**: Create searchable databases from document folders
- **Database Management**: Load and switch between different SQLite databases
- **Export Functionality**: Export search results as KML files for mapping
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

- **Frontend**: Flask web application with Jinja2 templates
- **Backend**: FastAPI service (unchanged from original)
- **Database**: SQLite with FTS5 support
- **Styling**: CSS3 with responsive design

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask application:
```bash
python run_flask_app.py
```

3. Open your browser and navigate to: http://127.0.0.1:5000

## Usage

### Loading a Database
1. Go to Settings
2. Upload a SQLite database file (.db, .sqlite, .sqlite3)
3. The database will be analyzed and made available for searching

### Creating a Database
1. Go to Create
2. Enter the path to a folder containing documents
3. Configure processing options (text extraction, coordinates, etc.)
4. Select file types to process
5. Click "Create Database"

### Searching
1. Go to Search
2. Enter your search terms
3. View results with highlighting and metadata
4. Export results as KML if coordinates are available

## File Structure

```
├── app.py                 # Main Flask application
├── run_flask_app.py      # Application runner
├── templates/            # Jinja2 templates
│   ├── base.html
│   ├── home.html
│   ├── search.html
│   ├── results.html
│   ├── settings.html
│   ├── create.html
│   ├── about.html
│   └── contact.html
├── static/              # Static assets
│   ├── css/
│   │   └── main.css
│   ├── js/
│   │   └── main.js
│   ├── images/
│   └── fonts/
├── run_app_dynamic.py   # FastAPI backend (unchanged)
└── database_operations/ # Database handling (unchanged)
```

## Differences from React Version

### Advantages
- **Deployment**: Easier to deploy in environments that don't support Node.js
- **Simplicity**: No build process required
- **Compatibility**: Works with any WSGI-compatible server
- **Resource Usage**: Lower memory footprint

### Limitations
- **Folder Selection**: Limited folder selection capabilities in web browsers
- **Real-time Updates**: No WebSocket support for real-time progress updates
- **File Drag & Drop**: Limited drag & drop functionality for folders

## Configuration

The application uses the same backend API as the original version. The FastAPI backend runs on port 8000 by default, and the Flask frontend runs on port 5000.

## Troubleshooting

### Backend Not Starting
- Check that port 8000 is available
- Ensure all Python dependencies are installed
- Check the console output for error messages

### Database Loading Issues
- Verify the SQLite file is not corrupted
- Check file permissions
- Ensure the database has the expected schema

### Search Not Working
- Verify a database is loaded
- Check that the backend is running
- Try refreshing the page

## Development

To run in development mode:
```bash
python app.py
```

This will start the Flask app in debug mode with auto-reload enabled.

## Deployment

For production deployment, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Or use a reverse proxy like Nginx to serve the static files and proxy API requests to the Flask application.
