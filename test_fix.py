#!/usr/bin/env python3
"""
Test script to verify database and file paths are working correctly
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_paths():
    """Test that all paths are correctly configured."""
    print("=== Testing Paths ===")
    
    # Test config paths
    from app.config import Config
    print(f"Database Path: {Config.DATABASE_PATH}")
    print(f"Storage Path: {Config.STORAGE_PATH}")
    print(f"Archive Path: {Config.ARCHIVE_PATH}")
    print(f"Temp Path: {Config.TEMP_PATH}")
    
    # Check if directories exist
    print(f"\n=== Directory Check ===")
    print(f"Database exists: {os.path.exists(Config.DATABASE_PATH)}")
    print(f"Storage exists: {os.path.exists(Config.STORAGE_PATH)}")
    print(f"Archive exists: {os.path.exists(Config.ARCHIVE_PATH)}")
    print(f"Temp exists: {os.path.exists(Config.TEMP_PATH)}")
    
    # Test DMS initialization
    print(f"\n=== DMS Test ===")
    try:
        from app.models.document_manager import DocumentManagementSystem
        dms = DocumentManagementSystem()
        print("DMS initialized successfully")
        print(f"DMS Storage Dir: {dms.storage_dir}")
        print(f"DMS DB Path: {dms.db_path}")
        
        # Test listing documents
        documents = dms.list_documents()
        print(f"Documents in DB: {len(documents)}")
        
        # Test listing image groups
        image_groups = dms.list_image_groups()
        print(f"Image Groups in DB: {len(image_groups)}")
        
        # Show sample data
        if documents:
            print(f"\n=== Sample Document ===")
            doc = documents[0]
            print(f"ID: {doc.get('id')}")
            print(f"Name: {doc.get('original_name')}")
            print(f"Stored Path: {doc.get('stored_path')}")
            print(f"File exists: {os.path.exists(doc.get('stored_path', ''))}")
        
        if image_groups:
            print(f"\n=== Sample Image Group ===")
            group = image_groups[0]
            print(f"ID: {group.get('id')}")
            print(f"Images: {len(group.get('images', []))}")
            for i, img in enumerate(group.get('images', [])):
                print(f"  Image {i+1}: {img.get('original_name')} -> {img.get('path')}")
                print(f"    File exists: {os.path.exists(img.get('path', ''))}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_paths() 