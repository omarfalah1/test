import os
import json
import shutil
import sqlite3
import uuid
import hashlib
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

class DocumentManagementSystem:
    def __init__(self, storage_dir: str = None, db_path: str = None):
        """Initialize the Document Management System.
        
        Args:
            storage_dir: Directory to store document files (uses config if None)
            db_path: Path to the SQLite database file (uses config if None)
        """
        # Import config here to avoid circular imports
        from app.config import Config
        
        self.storage_dir = storage_dir or Config.STORAGE_PATH
        self.db_path = db_path or Config.DATABASE_PATH
        self.archive_dir = Config.ARCHIVE_PATH
        self.temp_dir = Config.TEMP_PATH
        
        # Ensure directories exist
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
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
        
        # Add new columns to existing documents table if they don't exist
        self.migrate_database()

    def migrate_database(self):
        """Migrate existing database to add new columns."""
        with self.get_db_connection() as conn:
            # Check if new columns exist in documents table
            cursor = conn.execute("PRAGMA table_info(documents)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add new columns if they don't exist
            if 'file_size' not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN file_size INTEGER")
            if 'file_hash' not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN file_hash TEXT")
            if 'content_index' not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN content_index TEXT")
            
            # Create new tables for enhanced features
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS document_versions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    original_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    change_description TEXT,
                    file_size INTEGER,
                    file_hash TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_document_versions_doc_id ON document_versions(document_id);
                CREATE INDEX IF NOT EXISTS idx_document_versions_version ON document_versions(version_number);
                
                CREATE TABLE IF NOT EXISTS document_comments (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_comment_id TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_comment_id) REFERENCES document_comments(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_document_comments_doc_id ON document_comments(document_id);
                
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    permission_type TEXT NOT NULL CHECK (permission_type IN ('read', 'write', 'admin', 'delete')),
                    granted_at TEXT NOT NULL,
                    granted_by TEXT NOT NULL,
                    expires_at TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_permissions_doc_id ON user_permissions(document_id);
                
                CREATE TABLE IF NOT EXISTS document_activity (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL CHECK (activity_type IN ('view', 'download', 'edit', 'comment', 'approve', 'reject')),
                    activity_data TEXT,
                    created_at TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_document_activity_doc_id ON document_activity(document_id);
                CREATE INDEX IF NOT EXISTS idx_document_activity_user_id ON document_activity(user_id);
                CREATE INDEX IF NOT EXISTS idx_document_activity_created_at ON document_activity(created_at);
                
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    search_name TEXT NOT NULL,
                    search_query TEXT NOT NULL,
                    search_filters TEXT,
                    created_at TEXT NOT NULL,
                    last_used TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_saved_searches_user_id ON saved_searches(user_id);
            ''')
            
            # Add indexes for new columns
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_content ON documents(content_index)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_size ON documents(file_size)")
            except:
                pass  # Indexes might already exist

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def extract_text_content(self, file_path: str, file_type: str) -> str:
        """Extract text content from various file types for indexing."""
        if file_type == 'text':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        return f.read()
                except:
                    return ""
        # Add more file type handlers here (PDF, DOC, etc.)
        return ""

    def add_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None, created_by: str = None) -> str:
        """Add a new document to the system.
        
        Args:
            file_path: Path to the file to be added
            metadata: Optional dictionary of metadata
            created_by: User who created the document
            
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
            
            # Calculate file properties
            file_size = os.path.getsize(file_path)
            file_hash = self.calculate_file_hash(file_path)
            file_type = self.get_file_type(original_name)
            content_index = self.extract_text_content(file_path, file_type)
            
            # Convert metadata to JSON string
            metadata_str = json.dumps(metadata) if metadata else None

            # Copy file first
            shutil.copy2(file_path, stored_path)  # copy2 preserves metadata

            try:
                with self.get_db_connection() as conn:
                    conn.execute('''
                        INSERT INTO documents (id, original_name, stored_path, created_at, version, metadata, file_size, file_hash, content_index)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (doc_id, original_name, stored_path, created_at, version, metadata_str, file_size, file_hash, content_index))
                    
                    # Add initial version record
                    conn.execute('''
                        INSERT INTO document_versions (id, document_id, version_number, original_name, stored_path, 
                                                 created_at, created_by, file_size, file_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (str(uuid.uuid4()), doc_id, version, original_name, stored_path, 
                     created_at, created_by or 'system', file_size, file_hash))
                    
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
                SELECT id, original_name, stored_path, created_at, version, metadata, deleted, 
                       file_size, file_hash, content_index
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
                SELECT id, original_name, stored_path, created_at, version, metadata, deleted, 
                       file_size, file_hash, content_index
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

    def advanced_search(self, query: str = "", filters: Dict[str, Any] = None, user_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Advanced search with full-text search and filters.
        
        Args:
            query: Search query string
            filters: Dictionary of filters (date_range, file_type, file_size, status, etc.)
            user_id: User ID for permission checking
            limit: Maximum number of results
            
        Returns:
            List of matching documents and image groups
        """
        results = []
        
        # Search regular documents
        with self.get_db_connection() as conn:
            # Build the base query for documents
            base_query = """
                SELECT DISTINCT d.id, d.original_name, d.stored_path, d.created_at, d.version, 
                       d.metadata, d.file_size, d.file_hash, d.content_index
                FROM documents d
                LEFT JOIN user_permissions up ON d.id = up.document_id
                WHERE d.deleted = 0
            """
            
            params = []
            conditions = []
            
            # Add permission check if user_id provided
            if user_id:
                conditions.append("(up.user_id = ? OR up.permission_type = 'read' OR up.permission_type = 'admin')")
                params.append(user_id)
            
            # Add text search
            if query:
                search_conditions = []
                search_terms = query.split()
                for term in search_terms:
                    search_conditions.append("""
                        (d.original_name LIKE ? OR d.content_index LIKE ? OR 
                         d.metadata LIKE ?)
                    """)
                    params.extend([f'%{term}%', f'%{term}%', f'%{term}%'])
                conditions.append(f"({' OR '.join(search_conditions)})")
            
            # Add filters
            if filters:
                if 'date_from' in filters and filters['date_from']:
                    conditions.append("d.created_at >= ?")
                    params.append(filters['date_from'])
                
                if 'date_to' in filters and filters['date_to']:
                    conditions.append("d.created_at <= ?")
                    params.append(filters['date_to'])
                
                if 'file_type' in filters and filters['file_type']:
                    file_type = filters['file_type']
                    conditions.append("d.original_name LIKE ?")
                    params.append(f'%.{file_type}')
                
                if 'size_min' in filters and filters['size_min']:
                    conditions.append("d.file_size >= ?")
                    params.append(int(filters['size_min']) * 1024)  # Convert KB to bytes
                
                if 'size_max' in filters and filters['size_max']:
                    conditions.append("d.file_size <= ?")
                    params.append(int(filters['size_max']) * 1024)  # Convert KB to bytes
                
                if 'status' in filters and filters['status']:
                    conditions.append("d.metadata LIKE ?")
                    params.append(f'%"status": "{filters["status"]}"%')
            
            # Combine conditions
            if conditions:
                base_query += " AND " + " AND ".join(conditions)
            
            base_query += " ORDER BY d.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(base_query, params)
            columns = [col[0] for col in cursor.description]
            
            for row in cursor.fetchall():
                doc_dict = dict(zip(columns, row))
                if doc_dict['metadata']:
                    doc_dict['metadata'] = json.loads(doc_dict['metadata'])
                results.append(doc_dict)
        
        # Search image groups
        image_groups = self.list_image_groups()
        for group in image_groups:
            # Apply text search to image groups
            if query:
                search_terms = query.lower().split()
                group_name = group.get('metadata', {}).get('name', '').lower()
                group_tags = ' '.join(group.get('metadata', {}).get('tags', [])).lower()
                
                matches = False
                for term in search_terms:
                    if term in group_name or term in group_tags:
                        matches = True
                        break
                
                if not matches:
                    continue
            
            # Apply filters to image groups
            if filters:
                # Date filters
                if 'date_from' in filters and filters['date_from']:
                    group_date = group.get('created_at', '')
                    if group_date < filters['date_from']:
                        continue
                
                if 'date_to' in filters and filters['date_to']:
                    group_date = group.get('created_at', '')
                    if group_date > filters['date_to']:
                        continue
                
                # Status filter
                if 'status' in filters and filters['status']:
                    group_status = group.get('metadata', {}).get('status', '')
                    if group_status != filters['status']:
                        continue
            
            # Add image group to results
            group_result = {
                'id': group['id'],
                'original_name': group.get('metadata', {}).get('name', 'Image Group'),
                'stored_path': None,  # Image groups don't have a single stored path
                'created_at': group.get('created_at', ''),
                'version': 1,
                'metadata': group.get('metadata', {}),
                'file_size': None,  # Will be calculated if needed
                'file_hash': None,
                'content_index': None,
                'is_image_group': True,
                'image_count': len(group.get('images', []))
            }
            results.append(group_result)
        
        # Sort all results by creation date
        results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Limit results
        return results[:limit]

    def create_document_version(self, doc_id: str, new_file_path: str, created_by: str, change_description: str = "") -> str:
        """Create a new version of an existing document.
        
        Args:
            doc_id: ID of the original document
            new_file_path: Path to the new version file
            created_by: User creating the version
            change_description: Description of changes
            
        Returns:
            Version ID
        """
        if not os.path.isfile(new_file_path):
            raise FileNotFoundError(f"File does not exist: {new_file_path}")
        
        # Get current document info
        doc = self.get_document(doc_id)
        if not doc:
            raise Exception("Document not found")
        
        # Get next version number
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT MAX(version_number) FROM document_versions WHERE document_id = ?
            """, (doc_id,))
            max_version = cursor.fetchone()[0] or 0
            new_version = max_version + 1
        
        # Calculate file properties
        file_size = os.path.getsize(new_file_path)
        file_hash = self.calculate_file_hash(new_file_path)
        original_name = os.path.basename(new_file_path)
        
        # Store new version file
        version_id = str(uuid.uuid4())
        stored_name = f"{version_id}_{original_name}"
        stored_path = os.path.join(self.storage_dir, stored_name)
        shutil.copy2(new_file_path, stored_path)
        
        try:
            with self.get_db_connection() as conn:
                # Add version record
                conn.execute('''
                    INSERT INTO document_versions (id, document_id, version_number, original_name, stored_path, 
                                                 created_at, created_by, change_description, file_size, file_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (version_id, doc_id, new_version, original_name, stored_path, 
                     datetime.now().isoformat(), created_by, change_description, file_size, file_hash))
                
                # Update main document version
                conn.execute("UPDATE documents SET version = ? WHERE id = ?", (new_version, doc_id))
            
            return version_id
        except Exception as e:
            # Clean up file if database operation fails
            if os.path.exists(stored_path):
                os.remove(stored_path)
            raise Exception(f"Failed to create document version: {str(e)}")

    def get_document_versions(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all versions of a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            List of version dictionaries
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, document_id, version_number, original_name, stored_path, created_at, 
                       created_by, change_description, file_size, file_hash
                FROM document_versions 
                WHERE document_id = ? 
                ORDER BY version_number DESC
            """, (doc_id,))
            
            columns = [col[0] for col in cursor.description]
            versions = []
            
            for row in cursor.fetchall():
                version_dict = dict(zip(columns, row))
                versions.append(version_dict)
            
            return versions

    def add_document_comment(self, doc_id: str, user_id: str, comment: str, parent_comment_id: str = None) -> str:
        """Add a comment to a document.
        
        Args:
            doc_id: Document ID
            user_id: User ID
            comment: Comment text
            parent_comment_id: Parent comment ID for replies
            
        Returns:
            Comment ID
        """
        comment_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            conn.execute('''
                INSERT INTO document_comments (id, document_id, user_id, comment, created_at, parent_comment_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (comment_id, doc_id, user_id, comment, created_at, parent_comment_id))
        
        return comment_id

    def get_document_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all comments for a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            List of comment dictionaries
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, document_id, user_id, comment, created_at, parent_comment_id
                FROM document_comments 
                WHERE document_id = ? 
                ORDER BY created_at ASC
            """, (doc_id,))
            
            columns = [col[0] for col in cursor.description]
            comments = []
            
            for row in cursor.fetchall():
                comment_dict = dict(zip(columns, row))
                comments.append(comment_dict)
            
            return comments

    def set_document_permission(self, doc_id: str, user_id: str, permission_type: str, granted_by: str, expires_at: str = None) -> bool:
        """Set permission for a user on a document.
        
        Args:
            doc_id: Document ID
            user_id: User ID
            permission_type: Type of permission (read, write, admin, delete)
            granted_by: User granting the permission
            expires_at: Expiration date (optional)
            
        Returns:
            True if permission was set successfully
        """
        permission_id = str(uuid.uuid4())
        granted_at = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO user_permissions (id, user_id, document_id, permission_type, granted_at, granted_by, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (permission_id, user_id, doc_id, permission_type, granted_at, granted_by, expires_at))
        
        return True

    def check_user_permission(self, doc_id: str, user_id: str, required_permission: str = 'read') -> bool:
        """Check if a user has permission to access a document.
        
        Args:
            doc_id: Document ID
            user_id: User ID
            required_permission: Required permission level
            
        Returns:
            True if user has permission
        """
        permission_levels = {'read': 1, 'write': 2, 'admin': 3, 'delete': 4}
        required_level = permission_levels.get(required_permission, 1)
        
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT permission_type FROM user_permissions 
                WHERE document_id = ? AND user_id = ? AND (expires_at IS NULL OR expires_at > ?)
            """, (doc_id, user_id, datetime.now().isoformat()))
            
            result = cursor.fetchone()
            if result:
                user_level = permission_levels.get(result[0], 0)
                return user_level >= required_level
        
        return False

    def log_document_activity(self, doc_id: str, user_id: str, activity_type: str, activity_data: str = None, ip_address: str = None, user_agent: str = None) -> str:
        """Log user activity on a document.
        
        Args:
            doc_id: Document ID
            user_id: User ID
            activity_type: Type of activity
            activity_data: Additional activity data
            ip_address: User's IP address
            user_agent: User's browser agent
            
        Returns:
            Activity ID
        """
        activity_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            conn.execute('''
                INSERT INTO document_activity (id, document_id, user_id, activity_type, activity_data, created_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (activity_id, doc_id, user_id, activity_type, activity_data, created_at, ip_address, user_agent))
        
        return activity_id

    def save_search(self, user_id: str, search_name: str, search_query: str, search_filters: Dict[str, Any] = None) -> str:
        """Save a search query for later use.
        
        Args:
            user_id: User ID
            search_name: Name for the saved search
            search_query: Search query string
            search_filters: Search filters
            
        Returns:
            Search ID
        """
        search_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        filters_str = json.dumps(search_filters) if search_filters else None
        
        with self.get_db_connection() as conn:
            conn.execute('''
                INSERT INTO saved_searches (id, user_id, search_name, search_query, search_filters, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (search_id, user_id, search_name, search_query, filters_str, created_at))
        
        return search_id

    def get_saved_searches(self, user_id: str) -> List[Dict[str, Any]]:
        """Get saved searches for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of saved search dictionaries
        """
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, user_id, search_name, search_query, search_filters, created_at, last_used
                FROM saved_searches 
                WHERE user_id = ? 
                ORDER BY last_used DESC, created_at DESC
            """, (user_id,))
            
            columns = [col[0] for col in cursor.description]
            searches = []
            
            for row in cursor.fetchall():
                search_dict = dict(zip(columns, row))
                if search_dict['search_filters']:
                    search_dict['search_filters'] = json.loads(search_dict['search_filters'])
                searches.append(search_dict)
            
            return searches

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
