#!/usr/bin/env python3
"""
Test script for folder upload functionality
"""

import os
import tempfile
import requests
import json

def test_folder_upload():
    """Test the folder upload endpoint"""
    
    # Create a test folder structure
    test_dir = tempfile.mkdtemp()
    
    try:
        # Create some test files
        os.makedirs(os.path.join(test_dir, 'subfolder'), exist_ok=True)
        
        # Create test files
        with open(os.path.join(test_dir, 'test1.txt'), 'w') as f:
            f.write('This is test file 1')
        
        with open(os.path.join(test_dir, 'test2.txt'), 'w') as f:
            f.write('This is test file 2')
        
        with open(os.path.join(test_dir, 'subfolder', 'test3.txt'), 'w') as f:
            f.write('This is test file 3 in subfolder')
        
        print(f"Created test folder structure in: {test_dir}")
        print("Files created:")
        for root, dirs, files in os.walk(test_dir):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), test_dir)
                print(f"  {rel_path}")
        
        # Test the endpoint
        url = 'http://localhost:5000/create_database_from_folder'
        
        # Prepare form data
        files = []
        for root, dirs, filenames in os.walk(test_dir):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, test_dir)
                files.append(('files', (rel_path, open(file_path, 'rb'), 'text/plain')))
        
        data = {
            'db_name': 'test_database.db',
            'extract_text': 'true',
            'extract_coordinates': 'false',
            'include_images': 'false',
            'recursive': 'true',
            'file_types': ['txt']
        }
        
        print(f"\nTesting endpoint: {url}")
        print("Sending request...")
        
        response = requests.post(url, files=files, data=data, timeout=60)
        
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"✅ SUCCESS: {result.get('message')}")
                print(f"Database created at: {result.get('dbPath')}")
            else:
                print(f"❌ FAILED: {result.get('error')}")
        else:
            print(f"❌ HTTP ERROR: {response.status_code}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    finally:
        # Clean up
        try:
            for root, dirs, files in os.walk(test_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not file_path.endswith('.txt'):
                        continue
                    try:
                        os.remove(file_path)
                    except:
                        pass
            os.rmdir(os.path.join(test_dir, 'subfolder'))
            os.rmdir(test_dir)
        except:
            pass

if __name__ == '__main__':
    test_folder_upload()
