import os
import json
import shutil
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

class DocumentManagementSystem:
    def __init__(self, storage_dir: str = 'storage', db_path: str = 'dms_metadata.db'):
        """Initialize the Document Management System.
        
        Args:
            storage_dir: Directory to store document files
            db_path: Path to the SQLite database file
        """
        self.storage_dir = storage_dir
        self.db_path = db_path
        os.makedirs(storage_dir, exist_ok=True)
        self.setup_database()

    @contextmanager
    def get_db_connection(self):
        """Create a database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def setup_database(self):
        """Initialize the database schema with proper constraints."""
        sql = '''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            version INTEGER NOT NULL,
            metadata TEXT,
            deleted INTEGER DEFAULT 0 CHECK (deleted IN (0, 1))
        );
        CREATE INDEX IF NOT EXISTS idx_documents_deleted ON documents(deleted);
        CREATE TABLE IF NOT EXISTS archived_documents (
            id TEXT PRIMARY KEY,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            version INTEGER NOT NULL,
            metadata TEXT,
            deleted_at TEXT NOT NULL,
            deleted_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_archived_documents_id ON archived_documents(id);
        CREATE TABLE IF NOT EXISTS archived_image_groups (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            metadata TEXT,
            images TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            deleted_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_archived_image_groups_id ON archived_image_groups(id);
        '''
        with self.get_db_connection() as conn:
            conn.executescript(sql)
        sql = '''
        CREATE TABLE IF NOT EXISTS image_groups (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            metadata TEXT,
            images TEXT NOT NULL, -- JSON list of image info
            deleted INTEGER DEFAULT 0 CHECK (deleted IN (0, 1))
        );
        CREATE INDEX IF NOT EXISTS idx_image_groups_deleted ON image_groups(deleted);
        '''
        with self.get_db_connection() as conn:
            conn.executescript(sql)

    def add_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a new document to the system.
        
        Args:
            file_path: Path to the file to be added
            metadata: Optional dictionary of metadata
            
        Returns:
            Document ID of the added document
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            Exception: If there's an error adding the document
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")

        try:
            original_name = os.path.basename(file_path)
            doc_id = str(uuid.uuid4())
            stored_name = f"{doc_id}_{original_name}"
            stored_path = os.path.join(self.storage_dir, stored_name)
            created_at = datetime.now().isoformat()
            version = 1
            
            # Convert metadata to JSON string
            metadata_str = json.dumps(metadata) if metadata else None

            # Copy file first
            shutil.copy2(file_path, stored_path)  # copy2 preserves metadata

            try:
                with self.get_db_connection() as conn:
                    conn.execute('''
                        INSERT INTO documents (id, original_name, stored_path, created_at, version, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (doc_id, original_name, stored_path, created_at, version, metadata_str))
                return doc_id
            except Exception as e:
                # Clean up the copied file if database operation fails
                if os.path.exists(stored_path):
                    os.remove(stored_path)
                raise Exception(f"Failed to add document to database: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to add document: {str(e)}")

    def list_documents(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """List all documents in the system.
        
        Args:
            include_deleted: Whether to include soft-deleted documents
            
        Returns:
            List of document dictionaries
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, original_name, stored_path, created_at, version, metadata, deleted 
                FROM documents {}
                ORDER BY created_at DESC
            """.format("" if include_deleted else "WHERE deleted = 0"))
            
            columns = [col[0] for col in cursor.description]
            documents = []
            
            for row in cursor.fetchall():
                doc_dict = dict(zip(columns, row))
                if doc_dict['metadata']:
                    doc_dict['metadata'] = json.loads(doc_dict['metadata'])
                documents.append(doc_dict)
            
            return documents

    def get_file_type(self, filename: str) -> str:
        """Determine the type of file based on its extension."""
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.txt', '.md', '.py', '.json', '.csv', '.log']:
            return 'text'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            return 'image'
        elif ext in ['.pdf']:
            return 'pdf'
        return 'other'

    def get_file_content(self, stored_path: str, file_type: str) -> Optional[str]:
        """Get the content of a file based on its type."""
        if not os.path.exists(stored_path):
            return None
            
        if file_type == 'text':
            try:
                with open(stored_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return content if content else "Empty file"
            except UnicodeDecodeError:
                try:
                    # Try with different encoding if UTF-8 fails
                    with open(stored_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                        return content if content else "Empty file"
                except Exception:
                    return "Error: Could not read file content - encoding issue"
            except Exception:
                return "Error: Could not read file content"
        return None

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific document by ID.
        
        Args:
            doc_id: The ID of the document to retrieve
            
        Returns:
            Document dictionary if found, None otherwise
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, original_name, stored_path, created_at, version, metadata, deleted 
                FROM documents WHERE id = ?
            """, (doc_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            columns = [col[0] for col in cursor.description]
            doc_dict = dict(zip(columns, row))
            if doc_dict['metadata']:
                doc_dict['metadata'] = json.loads(doc_dict['metadata'])
            
            # Add file type information
            doc_dict['file_type'] = self.get_file_type(doc_dict['original_name'])
            
            # Add file content for text files
            if doc_dict['file_type'] == 'text':
                doc_dict['content'] = self.get_file_content(doc_dict['stored_path'], 'text')
            
            return doc_dict

    def soft_delete_document(self, doc_id: str) -> bool:
        """Soft delete a document.
        
        Args:
            doc_id: The ID of the document to delete
            
        Returns:
            True if document was deleted, False if not found
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("UPDATE documents SET deleted = 1 WHERE id = ? AND deleted = 0", (doc_id,))
            return cursor.rowcount > 0

    def restore_document(self, doc_id: str) -> bool:
        """Restore a soft-deleted document.
        
        Args:
            doc_id: The ID of the document to restore
            
        Returns:
            True if document was restored, False if not found
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("UPDATE documents SET deleted = 0 WHERE id = ? AND deleted = 1", (doc_id,))
            return cursor.rowcount > 0

    def update_metadata(self, doc_id: str, new_metadata: Dict[str, Any]) -> bool:
        """Update a document's metadata.
        
        Args:
            doc_id: The ID of the document to update
            new_metadata: New metadata dictionary
            
        Returns:
            True if metadata was updated, False if document not found
        """
        metadata_str = json.dumps(new_metadata) if new_metadata else None
        with self.get_db_connection() as conn:
            cursor = conn.execute(
                "UPDATE documents SET metadata = ? WHERE id = ?", 
                (metadata_str, doc_id)
            )
            return cursor.rowcount > 0

    def remove_document_permanently(self, doc_id: str) -> bool:
        """Permanently remove a document from the system.
        
        Args:
            doc_id: The ID of the document to remove
            
        Returns:
            True if document was removed, False if not found
            
        Raises:
            Exception: If there's an error removing the document
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("SELECT stored_path FROM documents WHERE id = ?", (doc_id,))
            result = cursor.fetchone()
            
            if not result:
                return False
                
            stored_path = result[0]
            try:
                if os.path.exists(stored_path):
                    os.remove(stored_path)
                cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                return True
            except Exception as e:
                raise Exception(f"Failed to remove document: {str(e)}")

    def archive_document(self, doc_id: str, archive_dir: str = 'archive', deleted_by: str = None) -> bool:
        """Archive a document: move file, insert metadata into archived_documents, and mark as deleted."""
        archive_dir_abs = os.path.abspath(archive_dir)
        os.makedirs(archive_dir_abs, exist_ok=True)
        print(f"[archive_document] Called for doc_id={doc_id}")
        with self.get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            if not row:
                print(f"[archive_document] Document not found: {doc_id}")
                return False
            columns = [col[0] for col in cursor.description]
            doc = dict(zip(columns, row))
            src_path = os.path.abspath(doc['stored_path'])
            archive_name = os.path.basename(doc['stored_path'])
            archive_path = os.path.join(archive_dir_abs, archive_name)
            print(f"[archive_document] src_path={src_path}")
            print(f"[archive_document] archive_path={archive_path}")
            if os.path.exists(src_path):
                print(f"[archive_document] Moving file...")
                shutil.move(src_path, archive_path)
            else:
                print(f"[archive_document] Source file does not exist: {src_path}")
                archive_path = src_path  # File missing, still archive metadata
            conn.execute('''
                INSERT OR REPLACE INTO archived_documents (id, original_name, stored_path, created_at, version, metadata, deleted_at, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc['id'], doc['original_name'], archive_path, doc['created_at'], doc['version'], doc['metadata'], datetime.now().isoformat(), deleted_by
            ))
            conn.execute("UPDATE documents SET deleted = 1 WHERE id = ?", (doc_id,))
            print(f"[archive_document] Archive complete for doc_id={doc_id}")
            return True

    def archive_documents(self, doc_ids: list, archive_dir: str = 'archive', deleted_by: str = None) -> int:
        """Archive multiple documents by IDs."""
        count = 0
        for doc_id in doc_ids:
            if self.archive_document(doc_id, archive_dir=archive_dir, deleted_by=deleted_by):
                count += 1
        return count

    def add_image_group(self, images: list, metadata: Optional[Dict[str, Any]] = None) -> str:
        import uuid
        group_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        metadata_str = json.dumps(metadata) if metadata else None
        images_json = json.dumps(images)
        with self.get_db_connection() as conn:
            conn.execute('''
                INSERT INTO image_groups (id, created_at, metadata, images)
                VALUES (?, ?, ?, ?)
            ''', (group_id, created_at, metadata_str, images_json))
        return group_id

    def list_image_groups(self, include_deleted: bool = False) -> list:
        with self.get_db_connection() as conn:
            cursor = conn.execute(f"""
                SELECT id, created_at, metadata, images, deleted
                FROM image_groups
                {'WHERE deleted = 0' if not include_deleted else ''}
                ORDER BY created_at DESC
            """)
            columns = [col[0] for col in cursor.description]
            groups = []
            for row in cursor.fetchall():
                group = dict(zip(columns, row))
                if group['metadata']:
                    group['metadata'] = json.loads(group['metadata'])
                group['images'] = json.loads(group['images'])
                groups.append(group)
            return groups

    def get_image_group(self, group_id: str) -> Optional[dict]:
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, created_at, metadata, images, deleted
                FROM image_groups WHERE id = ? AND deleted = 0
            """, (group_id,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [col[0] for col in cursor.description]
            group = dict(zip(columns, row))
            if group['metadata']:
                group['metadata'] = json.loads(group['metadata'])
            group['images'] = json.loads(group['images'])
            return group

    def soft_delete_image_group(self, group_id: str, deleted_by: str = None) -> bool:
        print(f"[soft_delete_image_group] Called for group_id={group_id}")
        return self.archive_image_group(group_id, deleted_by=deleted_by)

    def archive_image_group(self, group_id: str, archive_dir: str = 'archive', deleted_by: str = None) -> bool:
        """Archive an image group: move all images, insert metadata into archived_image_groups, and mark as deleted."""
        import json
        archive_dir_abs = os.path.abspath(archive_dir)
        os.makedirs(archive_dir_abs, exist_ok=True)
        print(f"[archive_image_group] Called for group_id={group_id}")
        with self.get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM image_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            if not row:
                print(f"[archive_image_group] Image group not found: {group_id}")
                return False
            columns = [col[0] for col in cursor.description]
            group = dict(zip(columns, row))
            images = json.loads(group['images']) if group['images'] else []
            moved_images = []
            for img in images:
                src_path = os.path.abspath(img['stored_path'])
                archive_name = os.path.basename(img['stored_path'])
                archive_path = os.path.join(archive_dir_abs, archive_name)
                print(f"[archive_image_group] Moving image: {src_path} -> {archive_path}")
                if os.path.exists(src_path):
                    shutil.move(src_path, archive_path)
                    img['stored_path'] = archive_path
                else:
                    print(f"[archive_image_group] Source image does not exist: {src_path}")
                    img['stored_path'] = src_path
                moved_images.append(img)
            conn.execute('''
                INSERT OR REPLACE INTO archived_image_groups (id, created_at, metadata, images, deleted_at, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                group['id'], group['created_at'], group['metadata'], json.dumps(moved_images), datetime.now().isoformat(), deleted_by
            ))
            conn.execute("UPDATE image_groups SET deleted = 1 WHERE id = ?", (group_id,))
            print(f"[archive_image_group] Archive complete for group_id={group_id}")
            return True

# Example usage
if __name__ == "__main__":
    # Initialize the document management system
    dms = DocumentManagementSystem()
    
    try:
        # Create a sample document for testing
        sample_content = "This is a sample document for testing."
        sample_file = "sample_document.txt"
        
        # Create a test file
        with open(sample_file, "w") as f:
            f.write(sample_content)
        
        # Add document with metadata
        doc_id = dms.add_document(
            sample_file,
            metadata={
                "department": "IT",
                "tags": ["test", "sample"],
                "status": "active"
            }
        )
        print(f"Added document with ID: {doc_id}")
        
        # List all documents
        print("\nListing all documents:")
        documents = dms.list_documents()
        for doc in documents:
            print(f"Document: {doc['original_name']}")
            print(f"Created: {doc['created_at']}")
            print(f"Metadata: {doc['metadata']}")
            print("---")
        
        if doc_id:
            # Get specific document
            doc = dms.get_document(doc_id)
            if doc:
                print(f"\nRetrieved document: {doc['original_name']}")
            
            # Update metadata
            updated = dms.update_metadata(doc_id, {
                "department": "HR",
                "status": "archived",
                "archived_date": datetime.now().isoformat()
            })
            print(f"Metadata updated: {updated}")
            
            # Soft delete
            deleted = dms.soft_delete_document(doc_id)
            print(f"Document soft deleted: {deleted}")
            
            # Restore
            restored = dms.restore_document(doc_id)
            print(f"Document restored: {restored}")
            
            # Remove permanently
            removed = dms.remove_document_permanently(doc_id)
            print(f"Document permanently removed: {removed}")
        
        # Clean up the test file
        if os.path.exists(sample_file):
            os.remove(sample_file)
            
    except Exception as e:
        print(f"Error: {str(e)}")
