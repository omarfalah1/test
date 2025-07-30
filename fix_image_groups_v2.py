#!/usr/bin/env python3
"""
Script to fix existing image groups data structure - Version 2
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_image_groups_v2():
    """Fix existing image groups by matching files by original names."""
    from app.config import Config
    
    db_path = Config.DATABASE_PATH
    storage_path = Config.STORAGE_PATH
    
    print("=== Fixing Image Groups V2 ===")
    print(f"Database: {db_path}")
    print(f"Storage: {storage_path}")
    
    # Get all files in storage
    storage_files = os.listdir(storage_path)
    print(f"Found {len(storage_files)} files in storage")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get all image groups
        cursor.execute("SELECT id, images FROM image_groups WHERE deleted = 0")
        groups = cursor.fetchall()
        
        print(f"Found {len(groups)} image groups to fix")
        
        for group_id, images_json in groups:
            print(f"\nProcessing group: {group_id}")
            
            try:
                images = json.loads(images_json)
                updated_images = []
                
                for img in images:
                    original_name = img.get('original_name', '')
                    print(f"  Looking for: {original_name}")
                    
                    # Find matching file in storage
                    matching_file = None
                    for filename in storage_files:
                        # Check if the original name is in the filename
                        if original_name in filename:
                            matching_file = filename
                            break
                    
                    if matching_file:
                        full_path = os.path.join(storage_path, matching_file)
                        print(f"    Found: {matching_file}")
                        
                        # Update image info
                        img['path'] = full_path
                        img['filename'] = matching_file
                        img['stored_path'] = full_path
                        img['stored_name'] = matching_file
                    else:
                        print(f"    Warning: Could not find file for {original_name}")
                        img['path'] = None
                        img['filename'] = original_name
                        img['stored_path'] = None
                        img['stored_name'] = None
                    
                    updated_images.append(img)
                
                # Update the database
                updated_json = json.dumps(updated_images)
                cursor.execute(
                    "UPDATE image_groups SET images = ? WHERE id = ?",
                    (updated_json, group_id)
                )
                print(f"  Updated group {group_id}")
                
            except Exception as e:
                print(f"  Error processing group {group_id}: {e}")
        
        # Commit changes
        conn.commit()
        print(f"\n=== Fix Complete ===")
        print(f"Updated {len(groups)} image groups")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_image_groups_v2() 