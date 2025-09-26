#!/usr/bin/env python3
"""
Simple test script for Flask application
"""

import requests
import time
import subprocess
import sys
import os

def test_flask_app():
    """Test the Flask application"""
    print("Testing CORE Scout Flask Application...")
    
    # Test if Flask app starts
    try:
        # Start the Flask app in a subprocess
        print("Starting Flask application...")
        flask_process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Wait for Flask to start
        time.sleep(5)
        
        # Test home page
        print("Testing home page...")
        response = requests.get("http://127.0.0.1:5000/", timeout=10)
        if response.status_code == 200:
            print("✓ Home page loads successfully")
        else:
            print(f"✗ Home page failed: {response.status_code}")
        
        # Test search page
        print("Testing search page...")
        response = requests.get("http://127.0.0.1:5000/search", timeout=10)
        if response.status_code == 200:
            print("✓ Search page loads successfully")
        else:
            print(f"✗ Search page failed: {response.status_code}")
        
        # Test settings page
        print("Testing settings page...")
        response = requests.get("http://127.0.0.1:5000/settings", timeout=10)
        if response.status_code == 200:
            print("✓ Settings page loads successfully")
        else:
            print(f"✗ Settings page failed: {response.status_code}")
        
        # Test create page
        print("Testing create page...")
        response = requests.get("http://127.0.0.1:5000/create", timeout=10)
        if response.status_code == 200:
            print("✓ Create page loads successfully")
        else:
            print(f"✗ Create page failed: {response.status_code}")
        
        # Test about page
        print("Testing about page...")
        response = requests.get("http://127.0.0.1:5000/about", timeout=10)
        if response.status_code == 200:
            print("✓ About page loads successfully")
        else:
            print(f"✗ About page failed: {response.status_code}")
        
        # Test contact page
        print("Testing contact page...")
        response = requests.get("http://127.0.0.1:5000/contact", timeout=10)
        if response.status_code == 200:
            print("✓ Contact page loads successfully")
        else:
            print(f"✗ Contact page failed: {response.status_code}")
        
        print("\nFlask application test completed!")
        
    except Exception as e:
        print(f"Error testing Flask app: {e}")
    finally:
        # Clean up
        try:
            flask_process.terminate()
            flask_process.wait(timeout=5)
        except:
            flask_process.kill()

if __name__ == '__main__':
    test_flask_app()
