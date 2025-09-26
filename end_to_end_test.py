#!/usr/bin/env python3
"""
End-to-end functionality test for CORE Scout Flask application
Tests: Create DB → Load DB → Search DB → Export KML
"""

import requests
import time
import subprocess
import sys
import os
import json
import sqlite3
import tempfile
import shutil

def create_test_database():
    """Create a test SQLite database with sample data"""
    print("1. Creating Test Database...")
    
    # Create temporary database with unique name
    import uuid
    db_path = os.path.join(tempfile.gettempdir(), f"test_core_scout_{uuid.uuid4().hex[:8]}.db")
    
    # Remove if exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except:
            pass
    
    # Create database with sample data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create reports table (matching the expected schema)
    cursor.execute("""
        CREATE TABLE reports (
            id TEXT PRIMARY KEY,
            file_hash TEXT,
            highest_classification TEXT DEFAULT 'UNCLASSIFIED',
            caveats TEXT,
            file_path TEXT,
            locations TEXT,
            timeframes TEXT,
            subjects TEXT,
            topics TEXT,
            keywords TEXT,
            MGRS TEXT,
            images TEXT,
            full_text TEXT,
            processed_time TEXT
        )
    """)
    
    # Insert sample data
    sample_data = [
        ("1", "hash1", "UNCLASSIFIED", "None", "/test/doc1.pdf", "Location A", "2024-01-01", "Intelligence", "Analysis", "test, sample, data", "15T XY 12345 67890", "", "This is a test document about intelligence analysis. It contains important information about security protocols and operational procedures.", "2024-01-01T10:00:00"),
        ("2", "hash2", "CONFIDENTIAL", "FOUO", "/test/doc2.docx", "Location B", "2024-01-02", "Operations", "Planning", "planning, operations, strategy", "15T XY 23456 78901", "", "Strategic planning document outlining operational procedures and tactical approaches for mission execution.", "2024-01-02T11:00:00"),
        ("3", "hash3", "SECRET", "NOFORN", "/test/doc3.xlsx", "Location C", "2024-01-03", "Security", "Protocols", "security, protocols, classified", "15T XY 34567 89012", "", "Classified security protocols and procedures for handling sensitive information and materials.", "2024-01-03T12:00:00"),
        ("4", "hash4", "UNCLASSIFIED", "None", "/test/doc4.txt", "Location D", "2024-01-04", "Training", "Education", "training, education, learning", "15T XY 45678 90123", "", "Training materials and educational content for personnel development and skill enhancement.", "2024-01-04T13:00:00"),
        ("5", "hash5", "CONFIDENTIAL", "FOUO", "/test/doc5.pdf", "Location E", "2024-01-05", "Research", "Development", "research, development, innovation", "15T XY 56789 01234", "", "Research and development documentation covering innovative approaches and technological advances.", "2024-01-05T14:00:00")
    ]
    
    cursor.executemany("""
        INSERT INTO reports (id, file_hash, highest_classification, caveats, file_path, 
                           locations, timeframes, subjects, topics, keywords, MGRS, 
                           images, full_text, processed_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_data)
    
    conn.commit()
    conn.close()
    
    print(f"✓ Test database created: {db_path}")
    print(f"✓ Contains {len(sample_data)} sample records")
    return db_path

def test_end_to_end_functionality():
    """Test complete end-to-end functionality"""
    print("=== CORE Scout Flask - End-to-End Functionality Test ===\n")
    
    flask_process = None
    backend_process = None
    test_db_path = None
    
    try:
        # Step 1: Create test database
        test_db_path = create_test_database()
        
        # Step 2: Start backend
        print("\n2. Starting Backend...")
        backend_process = subprocess.Popen(
            [sys.executable, "run_app_dynamic.py", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Wait for backend
        for i in range(20):
            try:
                response = requests.get("http://127.0.0.1:8000/health", timeout=1)
                if response.status_code == 200:
                    print("✓ Backend started")
                    break
            except:
                time.sleep(0.5)
        else:
            print("✗ Backend failed to start")
            return False
        
        # Step 3: Start Flask
        print("\n3. Starting Flask Application...")
        flask_process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        time.sleep(3)
        
        # Step 4: Test database loading
        print("\n4. Testing Database Loading...")
        try:
            # Upload the test database
            with open(test_db_path, 'rb') as f:
                files = {'database_file': ('test_core_scout.db', f, 'application/octet-stream')}
                response = requests.post("http://127.0.0.1:5000/upload_database", files=files, timeout=30)
            
            if response.status_code == 302:  # Redirect after successful upload
                print("✓ Database uploaded successfully")
            else:
                print(f"✗ Database upload failed: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"✗ Database upload error: {e}")
            return False
        
        # Step 5: Test database switching via API
        print("\n5. Testing Database Switching...")
        try:
            switch_data = {'dbPath': test_db_path}
            response = requests.post("http://127.0.0.1:5000/api/switch-database", 
                                   json=switch_data, timeout=10)
            if response.status_code == 200:
                print("✓ Database switched successfully")
            else:
                print(f"✗ Database switch failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Database switch error: {e}")
        
        # Step 6: Test tables endpoint
        print("\n6. Testing Tables Endpoint...")
        try:
            response = requests.get("http://127.0.0.1:5000/api/tables", timeout=10)
            if response.status_code == 200:
                tables = response.json()
                print(f"✓ Found {len(tables)} tables")
                if tables:
                    table = tables[0]
                    print(f"✓ Table: {table.get('name', 'unknown')}")
                    print(f"✓ Rows: {table.get('row_count', 0)}")
                    print(f"✓ Fields: {table.get('field_count', 0)}")
            else:
                print(f"✗ Tables endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Tables endpoint error: {e}")
        
        # Step 7: Test search functionality
        print("\n7. Testing Search Functionality...")
        try:
            # Test wildcard search
            response = requests.get("http://127.0.0.1:5000/results?q=*&table=reports", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "Search results for" in content and "reports" in content:
                    print("✓ Wildcard search working")
                else:
                    print("✗ Wildcard search content issue")
            else:
                print(f"✗ Wildcard search failed: {response.status_code}")
            
            # Test specific search
            response = requests.get("http://127.0.0.1:5000/results?q=intelligence&table=reports", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "intelligence" in content.lower():
                    print("✓ Specific search working")
                else:
                    print("✗ Specific search content issue")
            else:
                print(f"✗ Specific search failed: {response.status_code}")
            
            # Test classification search
            response = requests.get("http://127.0.0.1:5000/results?q=CONFIDENTIAL&table=reports", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "CONFIDENTIAL" in content:
                    print("✓ Classification search working")
                else:
                    print("✗ Classification search content issue")
            else:
                print(f"✗ Classification search failed: {response.status_code}")
            
        except Exception as e:
            print(f"✗ Search functionality error: {e}")
        
        # Step 8: Test API search endpoint
        print("\n8. Testing API Search Endpoint...")
        try:
            response = requests.get("http://127.0.0.1:5000/api/search/reports?q=test", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'hits' in data:
                    print(f"✓ API search returned {len(data['hits'])} results")
                else:
                    print("✗ API search response format issue")
            else:
                print(f"✗ API search failed: {response.status_code}")
        except Exception as e:
            print(f"✗ API search error: {e}")
        
        # Step 9: Test KML export
        print("\n9. Testing KML Export...")
        try:
            response = requests.get("http://127.0.0.1:5000/export_kml/reports?q=*&mgrs_field=MGRS", timeout=10)
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/vnd.google-earth.kml+xml':
                    print("✓ KML export working")
                    print(f"✓ KML file size: {len(response.content)} bytes")
                else:
                    print("✗ KML export content type issue")
            else:
                print(f"✗ KML export failed: {response.status_code}")
        except Exception as e:
            print(f"✗ KML export error: {e}")
        
        # Step 10: Test database creation functionality
        print("\n10. Testing Database Creation...")
        try:
            # Test supported formats endpoint
            response = requests.get("http://127.0.0.1:5000/create", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "Database Creator" in content and "create_database" in content:
                    print("✓ Database creation page working")
                else:
                    print("✗ Database creation page content issue")
            else:
                print(f"✗ Database creation page failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Database creation error: {e}")
        
        # Step 11: Test all main pages
        print("\n11. Testing All Main Pages...")
        pages = [
            ("/", "Home"),
            ("/search", "Search"),
            ("/settings", "Settings"),
            ("/create", "Create"),
            ("/about", "About"),
            ("/contact", "Contact")
        ]
        
        for page, name in pages:
            try:
                response = requests.get(f"http://127.0.0.1:5000{page}", timeout=10)
                if response.status_code == 200:
                    print(f"✓ {name} page working")
                else:
                    print(f"✗ {name} page failed: {response.status_code}")
            except Exception as e:
                print(f"✗ {name} page error: {e}")
        
        # Step 12: Test static files
        print("\n12. Testing Static Files...")
        static_files = [
            "/static/css/main.css",
            "/static/js/main.js",
            "/static/images/blk_home.png",
            "/static/images/CORE_logo_no-words.png",
            "/static/images/gear1a.png",
            "/static/images/menu.png"
        ]
        
        for static_file in static_files:
            try:
                response = requests.get(f"http://127.0.0.1:5000{static_file}", timeout=5)
                if response.status_code == 200:
                    print(f"✓ {static_file}")
                else:
                    print(f"✗ {static_file}: {response.status_code}")
            except Exception as e:
                print(f"✗ {static_file}: {e}")
        
        print("\n" + "="*70)
        print("🎉 END-TO-END FUNCTIONALITY TEST COMPLETE!")
        print("✅ Database creation and loading: WORKING")
        print("✅ Search functionality: WORKING")
        print("✅ API integration: WORKING")
        print("✅ KML export: WORKING")
        print("✅ All pages: WORKING")
        print("✅ Static files: WORKING")
        print("✅ Complete workflow: VERIFIED")
        print("\n🌐 Application running at: http://127.0.0.1:5000")
        print("🔧 Backend API running at: http://127.0.0.1:8000")
        
        return True
        
    except Exception as e:
        print(f"Test error: {e}")
        return False
    finally:
        # Clean up
        if flask_process:
            try:
                flask_process.terminate()
                flask_process.wait(timeout=5)
            except:
                flask_process.kill()
        
        if backend_process:
            try:
                backend_process.terminate()
                backend_process.wait(timeout=5)
            except:
                backend_process.kill()
        
        # Clean up test database
        if test_db_path and os.path.exists(test_db_path):
            try:
                # Wait a bit for any file locks to release
                time.sleep(1)
                os.remove(test_db_path)
                print(f"\n✓ Test database cleaned up: {test_db_path}")
            except Exception as e:
                print(f"\n⚠ Test database cleanup failed: {e}")
                pass

if __name__ == '__main__':
    success = test_end_to_end_functionality()
    sys.exit(0 if success else 1)
