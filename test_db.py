#!/usr/bin/env python3
"""
Test script to check database contents
"""

import sqlite3
import json

def test_database():
    """Test the database contents."""
    db_path = 'database/dms_metadata.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check documents table
        print("=== Documents Table ===")
        cursor.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]
        print(f"Total documents: {doc_count}")
        
        if doc_count > 0:
            cursor.execute("SELECT id, original_name, created_at, deleted FROM documents LIMIT 5")
            docs = cursor.fetchall()
            for doc in docs:
                print(f"  - ID: {doc[0]}, Name: {doc[1]}, Created: {doc[2]}, Deleted: {doc[3]}")
        
        # Check image_groups table
        print("\n=== Image Groups Table ===")
        cursor.execute("SELECT COUNT(*) FROM image_groups")
        img_count = cursor.fetchone()[0]
        print(f"Total image groups: {img_count}")
        
        if img_count > 0:
            cursor.execute("SELECT id, created_at, deleted FROM image_groups LIMIT 5")
            groups = cursor.fetchall()
            for group in groups:
                print(f"  - ID: {group[0]}, Created: {group[1]}, Deleted: {group[2]}")
        
        # Check table structure
        print("\n=== Table Structure ===")
        cursor.execute("PRAGMA table_info(documents)")
        columns = cursor.fetchall()
        print("Documents table columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_database() 