#!/usr/bin/env python3
"""
Debug script to see the actual data structure
"""

import os
import sys
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_data():
    """Debug the actual data structure."""
    from app.models.document_manager import DocumentManagementSystem
    
    dms = DocumentManagementSystem()
    
    print("=== Documents ===")
    documents = dms.list_documents()
    print(f"Count: {len(documents)}")
    
    if documents:
        doc = documents[0]
        print("Sample document structure:")
        for key, value in doc.items():
            if key == 'metadata' and value:
                print(f"  {key}: {json.loads(value) if isinstance(value, str) else value}")
            else:
                print(f"  {key}: {value}")
    
    print("\n=== Image Groups ===")
    image_groups = dms.list_image_groups()
    print(f"Count: {len(image_groups)}")
    
    if image_groups:
        group = image_groups[0]
        print("Sample image group structure:")
        for key, value in group.items():
            if key == 'metadata' and value:
                print(f"  {key}: {json.loads(value) if isinstance(value, str) else value}")
            elif key == 'images':
                print(f"  {key}: {len(value)} images")
                for i, img in enumerate(value[:2]):  # Show first 2 images
                    print(f"    Image {i+1}: {img}")
            else:
                print(f"  {key}: {value}")

if __name__ == "__main__":
    debug_data() 