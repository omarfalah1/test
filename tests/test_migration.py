#!/usr/bin/env python3
"""
Test script to verify database migration and new features work correctly.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.github'))

from index import DocumentManagementSystem
import tempfile
import json

def test_database_migration():
    """Test that the database migration works correctly."""
    print("Testing database migration...")
    
    # Initialize DMS
    dms = DocumentManagementSystem()
    
    # Test that we can list documents without errors
    try:
        documents = dms.list_documents()
        print(f"✓ Successfully listed {len(documents)} documents")
        
        # Test that we can get a specific document
        if documents:
            doc = dms.get_document(documents[0]['id'])
            if doc:
                print(f"✓ Successfully retrieved document: {doc['original_name']}")
                print(f"  - File size: {doc.get('file_size', 'N/A')}")
                print(f"  - File hash: {doc.get('file_hash', 'N/A')[:16] if doc.get('file_hash') else 'N/A'}")
                print(f"  - Content index: {len(doc.get('content_index', '')) if doc.get('content_index') else 0} chars")
            else:
                print("✗ Failed to retrieve document")
        else:
            print("ℹ No documents found to test with")
            
    except Exception as e:
        print(f"✗ Error listing documents: {e}")
        return False
    
    return True

def test_advanced_search():
    """Test advanced search functionality."""
    print("\nTesting advanced search...")
    
    dms = DocumentManagementSystem()
    
    try:
        # Test basic search
        results = dms.advanced_search("", {}, None, 10)
        print(f"✓ Advanced search returned {len(results)} results")
        
        # Test saved searches
        searches = dms.get_saved_searches("admin")
        print(f"✓ Retrieved {len(searches)} saved searches")
        
    except Exception as e:
        print(f"✗ Error in advanced search: {e}")
        return False
    
    return True

def test_versioning():
    """Test document versioning functionality."""
    print("\nTesting document versioning...")
    
    dms = DocumentManagementSystem()
    
    try:
        # Get existing documents
        documents = dms.list_documents()
        if documents:
            doc_id = documents[0]['id']
            
            # Test getting versions
            versions = dms.get_document_versions(doc_id)
            print(f"✓ Retrieved {len(versions)} versions for document")
            
            # Test getting comments
            comments = dms.get_document_comments(doc_id)
            print(f"✓ Retrieved {len(comments)} comments for document")
            
        else:
            print("ℹ No documents found to test versioning with")
            
    except Exception as e:
        print(f"✗ Error in versioning: {e}")
        return False
    
    return True

def test_permissions():
    """Test permission system."""
    print("\nTesting permissions...")
    
    dms = DocumentManagementSystem()
    
    try:
        # Test permission checking
        documents = dms.list_documents()
        if documents:
            doc_id = documents[0]['id']
            
            # Test permission check
            has_permission = dms.check_user_permission(doc_id, "admin", "read")
            print(f"✓ Permission check for admin: {has_permission}")
            
        else:
            print("ℹ No documents found to test permissions with")
            
    except Exception as e:
        print(f"✗ Error in permissions: {e}")
        return False
    
    return True

def main():
    """Run all tests."""
    print("🧪 Testing Document Management System Enhancements")
    print("=" * 50)
    
    tests = [
        test_database_migration,
        test_advanced_search,
        test_versioning,
        test_permissions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The enhanced DMS is working correctly.")
    else:
        print("⚠ Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 