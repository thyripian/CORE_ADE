#!/usr/bin/env python3
"""
Simple functionality test focusing on core features
"""

import requests
import time
import subprocess
import sys
import os
import json
import sqlite3
import tempfile
import uuid

def create_test_database():
    """Create a test SQLite database"""
    print("1. Creating Test Database...")
    
    db_path = os.path.join(tempfile.gettempdir(), f"test_{uuid.uuid4().hex[:8]}.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create simple test table
    cursor.execute("""
        CREATE TABLE test_data (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT,
            classification TEXT
        )
    """)
    
    # Insert test data
    test_data = [
        (1, "Document 1", "This is a test document about intelligence", "UNCLASSIFIED"),
        (2, "Document 2", "This is a confidential report", "CONFIDENTIAL"),
        (3, "Document 3", "This is a secret document", "SECRET"),
        (4, "Document 4", "This is about operations", "UNCLASSIFIED"),
        (5, "Document 5", "This is about security protocols", "CONFIDENTIAL")
    ]
    
    cursor.executemany("INSERT INTO test_data VALUES (?, ?, ?, ?)", test_data)
    conn.commit()
    conn.close()
    
    print(f"✓ Test database created: {db_path}")
    return db_path

def test_core_functionality():
    """Test core functionality"""
    print("=== CORE Scout Flask - Core Functionality Test ===\n")
    
    flask_process = None
    backend_process = None
    test_db_path = None
    
    try:
        # Create test database
        test_db_path = create_test_database()
        
        # Start backend
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
        
        # Start Flask
        print("\n3. Starting Flask...")
        flask_process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        time.sleep(3)
        
        # Test 1: All pages load
        print("\n4. Testing Page Loading...")
        pages = [
            ("/", "Home"),
            ("/search", "Search"),
            ("/settings", "Settings"),
            ("/create", "Create"),
            ("/about", "About"),
            ("/contact", "Contact")
        ]
        
        all_pages_ok = True
        for page, name in pages:
            try:
                response = requests.get(f"http://127.0.0.1:5000{page}", timeout=10)
                if response.status_code == 200:
                    print(f"✓ {name} page")
                else:
                    print(f"✗ {name} page: {response.status_code}")
                    all_pages_ok = False
            except Exception as e:
                print(f"✗ {name} page: {e}")
                all_pages_ok = False
        
        # Test 2: Backend integration
        print("\n5. Testing Backend Integration...")
        try:
            # Test health endpoint
            response = requests.get("http://127.0.0.1:5000/api/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Backend health: {data.get('status', 'unknown')}")
            else:
                print(f"✗ Backend health: {response.status_code}")
                all_pages_ok = False
        except Exception as e:
            print(f"✗ Backend integration: {e}")
            all_pages_ok = False
        
        # Test 3: Database switching
        print("\n6. Testing Database Switching...")
        try:
            switch_data = {'dbPath': test_db_path}
            response = requests.post("http://127.0.0.1:5000/api/switch-database", 
                                   json=switch_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Database switched: {data.get('message', 'Success')}")
            else:
                print(f"✗ Database switch: {response.status_code}")
                all_pages_ok = False
        except Exception as e:
            print(f"✗ Database switch: {e}")
            all_pages_ok = False
        
        # Test 4: Tables endpoint
        print("\n7. Testing Tables Endpoint...")
        try:
            response = requests.get("http://127.0.0.1:5000/api/tables", timeout=10)
            if response.status_code == 200:
                tables = response.json()
                print(f"✓ Found {len(tables)} tables")
                if tables:
                    table = tables[0]
                    print(f"✓ Table: {table.get('name', 'unknown')} ({table.get('row_count', 0)} rows)")
            else:
                print(f"✗ Tables endpoint: {response.status_code}")
                all_pages_ok = False
        except Exception as e:
            print(f"✗ Tables endpoint: {e}")
            all_pages_ok = False
        
        # Test 5: Search functionality
        print("\n8. Testing Search Functionality...")
        try:
            # Test search results page
            response = requests.get("http://127.0.0.1:5000/results?q=test&table=test_data", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "Search results for" in content:
                    print("✓ Search results page")
                else:
                    print("✗ Search results content")
                    all_pages_ok = False
            else:
                print(f"✗ Search results: {response.status_code}")
                all_pages_ok = False
            
            # Test API search
            response = requests.get("http://127.0.0.1:5000/api/search/test_data?q=test", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ API search: {len(data.get('hits', []))} results")
            else:
                print(f"✗ API search: {response.status_code}")
                all_pages_ok = False
        except Exception as e:
            print(f"✗ Search functionality: {e}")
            all_pages_ok = False
        
        # Test 6: Static files
        print("\n9. Testing Static Files...")
        static_files = [
            "/static/css/main.css",
            "/static/js/main.js",
            "/static/images/blk_home.png",
            "/static/images/CORE_logo_no-words.png"
        ]
        
        static_ok = True
        for static_file in static_files:
            try:
                response = requests.get(f"http://127.0.0.1:5000{static_file}", timeout=5)
                if response.status_code == 200:
                    print(f"✓ {static_file}")
                else:
                    print(f"✗ {static_file}: {response.status_code}")
                    static_ok = False
            except Exception as e:
                print(f"✗ {static_file}: {e}")
                static_ok = False
        
        # Summary
        print("\n" + "="*60)
        if all_pages_ok and static_ok:
            print("🎉 CORE FUNCTIONALITY TEST PASSED!")
            print("✅ All pages load correctly")
            print("✅ Backend integration working")
            print("✅ Database operations functional")
            print("✅ Search functionality working")
            print("✅ Static files served correctly")
            print("\n🌐 Application: http://127.0.0.1:5000")
            print("🔧 Backend API: http://127.0.0.1:8000")
            return True
        else:
            print("❌ Some functionality failed")
            return False
        
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
                time.sleep(1)
                os.remove(test_db_path)
                print(f"\n✓ Test database cleaned up")
            except:
                pass

if __name__ == '__main__':
    success = test_core_functionality()
    sys.exit(0 if success else 1)
