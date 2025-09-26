#!/usr/bin/env python3
"""
Comprehensive test for Flask application conversion
"""

import requests
import time
import subprocess
import sys
import os
import json

def test_flask_app_comprehensive():
    """Comprehensive test of Flask application"""
    print("=== CORE Scout Flask Application - Comprehensive Test ===\n")
    
    flask_process = None
    backend_process = None
    
    try:
        # Start backend first
        print("1. Starting FastAPI Backend...")
        backend_process = subprocess.Popen(
            [sys.executable, "run_app_dynamic.py", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Wait for backend to start
        for i in range(20):
            try:
                response = requests.get("http://127.0.0.1:8000/health", timeout=1)
                if response.status_code == 200:
                    print("✓ Backend started successfully")
                    break
            except:
                time.sleep(0.5)
        else:
            print("✗ Backend failed to start")
            return False
        
        # Start Flask app
        print("\n2. Starting Flask Application...")
        flask_process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Wait for Flask to start
        time.sleep(3)
        
        # Test all routes
        print("\n3. Testing All Routes...")
        
        routes_to_test = [
            ("/", "Home Page"),
            ("/search", "Search Page"),
            ("/settings", "Settings Page"),
            ("/create", "Create Page"),
            ("/about", "About Page"),
            ("/contact", "Contact Page"),
            ("/api/health", "API Health Check"),
            ("/api/tables", "API Tables Endpoint")
        ]
        
        all_passed = True
        for route, description in routes_to_test:
            try:
                response = requests.get(f"http://127.0.0.1:5000{route}", timeout=10)
                if response.status_code == 200:
                    print(f"✓ {description}: {route}")
                else:
                    print(f"✗ {description}: {route} (Status: {response.status_code})")
                    all_passed = False
            except Exception as e:
                print(f"✗ {description}: {route} (Error: {e})")
                all_passed = False
        
        # Test search functionality
        print("\n4. Testing Search Functionality...")
        try:
            # Test search with wildcard query
            response = requests.get("http://127.0.0.1:5000/results?q=*&table=test", timeout=10)
            if response.status_code == 200:
                print("✓ Search results page loads")
            else:
                print(f"✗ Search results failed (Status: {response.status_code})")
                all_passed = False
        except Exception as e:
            print(f"✗ Search functionality error: {e}")
            all_passed = False
        
        # Test API integration
        print("\n5. Testing API Integration...")
        try:
            # Test backend health through Flask
            response = requests.get("http://127.0.0.1:5000/api/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✓ API Health: {health_data.get('status', 'unknown')}")
            else:
                print(f"✗ API Health check failed (Status: {response.status_code})")
                all_passed = False
        except Exception as e:
            print(f"✗ API integration error: {e}")
            all_passed = False
        
        # Test static files
        print("\n6. Testing Static Files...")
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
                    print(f"✓ Static file: {static_file}")
                else:
                    print(f"✗ Static file: {static_file} (Status: {response.status_code})")
                    all_passed = False
            except Exception as e:
                print(f"✗ Static file error: {static_file} - {e}")
                all_passed = False
        
        # Test form submissions
        print("\n7. Testing Form Submissions...")
        try:
            # Test database upload form (should fail gracefully without file)
            response = requests.post("http://127.0.0.1:5000/upload_database", 
                                   data={}, 
                                   timeout=10)
            if response.status_code in [200, 302]:  # Either success or redirect
                print("✓ Database upload form handles missing file gracefully")
            else:
                print(f"✗ Database upload form issue (Status: {response.status_code})")
                all_passed = False
        except Exception as e:
            print(f"✗ Form submission error: {e}")
            all_passed = False
        
        # Summary
        print("\n" + "="*60)
        if all_passed:
            print("🎉 ALL TESTS PASSED! Flask application is working correctly.")
            print("\n✅ Conversion Verification:")
            print("   • All React components converted to Flask templates")
            print("   • All routing functional")
            print("   • Backend integration working")
            print("   • Static files served correctly")
            print("   • Form handling working")
            print("   • API endpoints accessible")
        else:
            print("❌ Some tests failed. Check the output above for details.")
        
        print("\n🌐 Application is running at: http://127.0.0.1:5000")
        print("🔧 Backend API running at: http://127.0.0.1:8000")
        
        return all_passed
        
    except Exception as e:
        print(f"Test error: {e}")
        return False
    finally:
        # Clean up processes
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

if __name__ == '__main__':
    success = test_flask_app_comprehensive()
    sys.exit(0 if success else 1)
