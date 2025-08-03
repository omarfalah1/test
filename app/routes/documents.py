"""
Document management routes

This module handles all document-related operations including:
- Document listing and filtering
- Document uploads (single files and image groups)
- Document viewing, downloading, and previewing
- Document status management
- Document deletion
- Comments and metadata management
"""

# Standard library imports
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file, session
import os
import zipfile
import tempfile
from datetime import datetime, timedelta
from uuid import uuid4

# Local application imports
from app.models.document_manager import DocumentManagementSystem
from app.utils.decorators import login_required, permission_required
from app.config import Config

# Create Flask blueprint for document routes
bp = Blueprint('documents', __name__)

# Initialize the document management system
dms = DocumentManagementSystem()

def preserve_filters_redirect():
    """
    Helper function to preserve current filter state when redirecting.
    
    This function extracts filter parameters from the current page's URL
    and builds a redirect URL that maintains the filtered view.
    """
    current_filters = {}
    
    # Get filter parameters from the current page
    referer = request.headers.get('Referer', '')
    if referer:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(referer)
        query_params = parse_qs(parsed_url.query)
        
        # Extract filter parameters
        filter_keys = ['status', 'uploader', 'sort', 'search']
        for key in filter_keys:
            if key in query_params:
                current_filters[key] = query_params[key][0]
    
    # Build the redirect URL with preserved filters
    redirect_url = url_for('documents.index')
    if current_filters:
        query_string = '&'.join([f"{k}={v}" for k, v in current_filters.items() if v])
        if query_string:
            redirect_url += f"?{query_string}"
    
    return redirect_url

@bp.route('/')
@login_required
def index():
    """
    Main documents page - displays filtered list of documents and image groups.
    
    This route:
    1. Retrieves all documents and image groups from the database
    2. Filters them based on user permissions (ownership and sharing)
    3. Applies search, status, and uploader filters
    4. Sorts the results
    5. Renders the main documents page
    """
    # Get all documents and image groups from the database
    documents = dms.list_documents()
    image_groups = dms.list_image_groups()
    
    # Get current user information from session
    current_user = session.get('username')
    current_role = session.get('role')
    
    # ===== DOCUMENT FILTERING BY PERMISSIONS =====
    # All users (including admins) can only see documents they uploaded or were sent to them
    # This ensures security and privacy - users only see their own content and shared content
    filtered_documents = []
    for doc in documents:
        # Extract metadata about who uploaded the document and who it was sent to
        doc_uploader = doc.get('metadata', {}).get('uploaded_by', '')
        doc_recipients = doc.get('metadata', {}).get('recipients', [])
        
        # Skip documents without proper metadata (they shouldn't be visible to anyone)
        # This prevents access to documents with missing or corrupted metadata
        if not doc_uploader:
            continue
            
        # User can see if they uploaded it or if they're in the recipients list
        # This is the core permission logic: ownership OR sharing
        if doc_uploader == current_user or current_user in doc_recipients:
            filtered_documents.append(doc)
    
    # Replace the full document list with the filtered list
    documents = filtered_documents
    
    # ===== IMAGE GROUP FILTERING BY PERMISSIONS =====
    # Apply the same filtering logic to image groups
    filtered_image_groups = []
    for group in image_groups:
        # Extract metadata about who uploaded the image group and who it was sent to
        group_uploader = group.get('metadata', {}).get('uploaded_by', '')
        group_recipients = group.get('metadata', {}).get('recipients', [])
        
        # Skip image groups without proper metadata
        if not group_uploader:
            continue
            
        # User can see if they uploaded it or if they're in the recipients list
        if group_uploader == current_user or current_user in group_recipients:
            filtered_image_groups.append(group)
    
    # Replace the full image group list with the filtered list
    image_groups = filtered_image_groups
    
    # ===== URL PARAMETER FILTERING =====
    # Get filter parameters from the URL query string
    # These allow users to further filter the already permission-filtered results
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')
    uploader_filter = request.args.get('uploader', 'all')
    sort_by = request.args.get('sort', 'date_desc')
    
    # ===== BUILD UPLOADER DROPDOWN OPTIONS =====
    # Collect all unique uploaders from the filtered documents for the filter dropdown
    all_uploaders = set()
    for doc in documents:
        if doc.get('metadata', {}).get('uploaded_by'):
            all_uploaders.add(doc['metadata']['uploaded_by'])
    for group in image_groups:
        if group.get('metadata', {}).get('uploaded_by'):
            all_uploaders.add(group['metadata']['uploaded_by'])
    all_uploaders = sorted(list(all_uploaders))
    
    # ===== APPLY SEARCH FILTERS TO REGULAR DOCUMENTS =====
    # Filter documents by search query (searches in document names)
    if search_query:
        documents = [doc for doc in documents if search_query.lower() in doc.get('original_name', '').lower()]
    
    # Filter documents by status (pending, approved, rejected, active)
    if status_filter != 'all':
        documents = [doc for doc in documents if doc.get('metadata', {}).get('status') == status_filter]
    
    # Filter documents by uploader
    if uploader_filter != 'all':
        documents = [doc for doc in documents if doc.get('metadata', {}).get('uploaded_by') == uploader_filter]
    
    # ===== APPLY SEARCH FILTERS TO IMAGE GROUPS =====
    # Filter image groups by search query (searches in group names and tags)
    if search_query:
        filtered_image_groups = []
        for group in image_groups:
            group_name = group.get('metadata', {}).get('name', '').lower()
            group_tags = ' '.join(group.get('metadata', {}).get('tags', [])).lower()
            if (search_query.lower() in group_name or 
                search_query.lower() in group_tags):
                filtered_image_groups.append(group)
        image_groups = filtered_image_groups
    
    # Filter image groups by status
    if status_filter != 'all':
        image_groups = [group for group in image_groups if group.get('metadata', {}).get('status') == status_filter]
    
    # Filter image groups by uploader
    if uploader_filter != 'all':
        image_groups = [group for group in image_groups if group.get('metadata', {}).get('uploaded_by') == uploader_filter]
    
    # ===== APPLY SORTING =====
    # Sort both documents and image groups based on user preference
    if sort_by == 'date_asc':
        # Sort by creation date, oldest first
        documents.sort(key=lambda x: x.get('created_at', ''))
        image_groups.sort(key=lambda x: x.get('created_at', ''))
    elif sort_by == 'date_desc':
        # Sort by creation date, newest first (default)
        documents.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        image_groups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    elif sort_by == 'uploader':
        # Sort alphabetically by uploader name
        documents.sort(key=lambda x: x.get('metadata', {}).get('uploaded_by', ''))
        image_groups.sort(key=lambda x: x.get('metadata', {}).get('uploaded_by', ''))
    elif sort_by == 'status':
        # Sort by document status
        documents.sort(key=lambda x: x.get('metadata', {}).get('status', ''))
        image_groups.sort(key=lambda x: x.get('metadata', {}).get('status', ''))
    
    # ===== SEPARATE REGULAR DOCUMENTS FROM IMAGE GROUPS =====
    # Image groups are stored as documents with a special flag, so we need to separate them
    regular_docs = [doc for doc in documents if not doc.get('group_images')]
    
    # ===== CREATE SAMPLE DATA FOR TESTING =====
    # If no documents exist, create a sample document for testing purposes
    # This helps users understand how the system works
    if not documents and not image_groups:
        # Create sample metadata for the test document
        sample_metadata = {
            'department': 'IT',
            'tags': ['sample', 'test'],
            'status': 'active',
            'uploaded_by': session.get('username', 'admin'),
            'upload_date': datetime.now().isoformat()
        }
        
        # Create a temporary sample text file
        sample_file_path = os.path.join(Config.TEMP_PATH, 'sample_document.txt')
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        with open(sample_file_path, 'w') as f:
            f.write('This is a sample document for testing the DMS system.')
        
        try:
            # Add the sample document to the database
            dms.add_document(sample_file_path, metadata=sample_metadata, created_by=session.get('username', 'admin'))
            os.remove(sample_file_path)  # Clean up the temporary file
            flash('Sample document created for testing!')
            
            # Refresh the documents list to include the new sample document
            documents = dms.list_documents()
            regular_docs = [doc for doc in documents if not doc.get('group_images')]
            image_groups = dms.list_image_groups()
        except Exception as e:
            flash(f'Error creating sample document: {str(e)}')
    
    # Debug information removed - filtering is working correctly
    
    # ===== RENDER THE TEMPLATE =====
    # Pass all the processed data to the template for rendering
    return render_template('index.html', 
                         documents=regular_docs, 
                         image_groups=image_groups,
                         search_query=search_query,
                         status_filter=status_filter,
                         uploader_filter=uploader_filter,
                         sort_by=sort_by,
                         all_uploaders=all_uploaders,
                         role=session.get('role'),
                         Config=Config)

@bp.route('/upload', methods=['POST'])
@login_required
def upload_document():
    """
    Upload a document or image group.
    
    This route handles two types of uploads:
    1. Image groups (multiple images uploaded together)
    2. Single documents (any file type)
    
    The route also enforces upload restrictions:
    - Regular users can send documents to admins
    - Admins can only upload documents for themselves
    """
    # ===== HANDLE IMAGE GROUP UPLOADS =====
    # Check if this is an image group upload (multiple images)
    files = request.files.getlist('images')
    if files and any(file.filename for file in files):
        # Process each uploaded image
        image_infos = []
        for file in files:
            if file and file.filename:
                # Save the file to a temporary location first
                temp_path = os.path.join(Config.TEMP_PATH, file.filename)
                os.makedirs(Config.TEMP_PATH, exist_ok=True)
                file.save(temp_path)
                
                # Generate a unique filename to prevent conflicts
                stored_name = f"{uuid4()}_{file.filename}"
                stored_path = os.path.join(Config.STORAGE_PATH, stored_name)
                
                # Move the file from temp to permanent storage
                os.rename(temp_path, stored_path)
                
                # Create metadata for this image
                image_infos.append({
                    'original_name': file.filename,
                    'stored_path': stored_path,
                    'filename': stored_name,
                    'path': stored_path
                })
        
        # Validate that at least one image was processed
        if not image_infos:
            flash('No images selected')
            return redirect(url_for('documents.index'))
        
        # ===== APPLY UPLOAD RESTRICTIONS =====
        # Get user information for permission checking
        role = session.get('role')
        username = session.get('username')
        
        if role in ['employee', 'omar', 'pola']:
            # Regular users: documents start as pending and can be sent to admins
            status = 'pending'
            uploaded_by = username
            
            # Regular users can send documents to admins
            recipients = request.form.getlist('recipients')
            # Filter to only allow sending to admins (security measure)
            admin_users = [user for user, info in Config.USERS.items() if info['role'] == 'admin']
            recipients = [r for r in recipients if r in admin_users]
        else:
            # Admins: documents are active by default and cannot be sent to users
            status = request.form.get('status', 'active')
            uploaded_by = request.form.get('uploaded_by', username)
            # Admins cannot upload documents to users - they can only upload for themselves
            recipients = []
        
        # ===== CREATE METADATA =====
        # Build the metadata object with all document information
        metadata = {
            'department': request.form.get('department', ''),
            'tags': request.form.get('tags', '').split(','),
            'status': status,
            'uploaded_by': uploaded_by,
            'upload_date': datetime.now().isoformat(),
            'recipients': recipients
        }
        
        # Add the image group to the database
        dms.add_image_group(image_infos, metadata=metadata)
        flash(f'{len(image_infos)} images uploaded successfully!')
        return redirect(url_for('documents.index'))
    
    # ===== HANDLE SINGLE DOCUMENT UPLOADS =====
    # Check if this is a single document upload
    if 'document' not in request.files:
        flash('No file selected')
        return redirect(url_for('documents.index'))
    
    file = request.files['document']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('documents.index'))
    
    try:
        # Save the file to a temporary location
        temp_path = os.path.join(Config.TEMP_PATH, file.filename)
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        file.save(temp_path)
        
        # ===== APPLY UPLOAD RESTRICTIONS (SAME AS IMAGE GROUPS) =====
        role = session.get('role')
        username = session.get('username')
        
        if role in ['employee', 'omar', 'pola']:
            # Regular users: documents start as pending and can be sent to admins
            status = 'pending'
            uploaded_by = username
            
            # Regular users can send documents to admins
            recipients = request.form.getlist('recipients')
            # Filter to only allow sending to admins
            admin_users = [user for user, info in Config.USERS.items() if info['role'] == 'admin']
            recipients = [r for r in recipients if r in admin_users]
        else:
            # Admins: documents are active by default and cannot be sent to users
            status = request.form.get('status', 'active')
            uploaded_by = request.form.get('uploaded_by', username)
            # Admins cannot upload documents to users - they can only upload for themselves
            recipients = []
        
        # ===== CREATE METADATA =====
        metadata = {
            'department': request.form.get('department', ''),
            'tags': request.form.get('tags', '').split(','),
            'status': status,
            'uploaded_by': uploaded_by,
            'upload_date': datetime.now().isoformat(),
            'recipients': recipients
        }
        
        # Add the document to the database
        dms.add_document(temp_path, metadata=metadata, created_by=username)
        os.remove(temp_path)  # Clean up the temporary file
        flash('Document uploaded successfully!')
    except Exception as e:
        flash(f'Error uploading document: {str(e)}')
    
    return redirect(url_for('documents.index'))

@bp.route('/document/<doc_id>')
@login_required
@permission_required('read')
def view_document(doc_id):
    """
    View a specific document.
    
    This route handles both regular documents and image groups.
    For image groups, it shows one image at a time with navigation controls.
    """
    # ===== TRY TO GET AS REGULAR DOCUMENT FIRST =====
    doc = dms.get_document(doc_id)
    
    if not doc:
        # ===== TRY TO GET AS IMAGE GROUP =====
        doc = dms.get_image_group(doc_id)
        if not doc:
            flash('Document not found')
            return redirect(url_for('documents.index'))
        
        # ===== HANDLE IMAGE GROUP DISPLAY =====
        # Get which image to show (default to first image)
        img_index = request.args.get('img', 0, type=int)
        if img_index >= len(doc['images']):
            img_index = 0
        
        # Create a document-like structure for the current image
        # This allows the template to handle image groups the same way as regular documents
        current_image = doc['images'][img_index]
        doc = {
            'id': doc['id'],
            'name': f"{doc['metadata'].get('name', 'Image Group')} (Image {img_index + 1})",
            'upload_date': doc['metadata'].get('upload_date', doc['created_at']),
            'uploaded_by': doc['metadata'].get('uploaded_by', 'Unknown'),
            'status': doc['metadata'].get('status', 'active'),
            'file_type': 'image',
            'file_size': None,
            'file_hash': None,
            'content_index': None,
            'group_images': doc['images'],  # All images in the group
            'current_image_index': img_index,  # Which image is currently shown
            'current_image': current_image,  # The current image data
            'metadata': doc['metadata']  # Include the original metadata
        }
    
    # ===== GET COMMENTS FOR THE DOCUMENT =====
    comments = dms.get_document_comments(doc_id)
    
    # Render the document view template
    return render_template('documents/view.html', doc=doc, comments=comments)

@bp.route('/document/<doc_id>/preview')
def preview_document(doc_id):
    """
    Preview a document (serve the file directly to the browser).
    
    This route serves files for inline viewing in the browser.
    """
    # ===== TRY TO GET AS REGULAR DOCUMENT FIRST =====
    doc = dms.get_document(doc_id)
    
    if not doc:
        # ===== TRY TO GET AS IMAGE GROUP =====
        doc = dms.get_image_group(doc_id)
        if not doc:
            return "Document not found", 404
        
        # ===== HANDLE IMAGE GROUP PREVIEW =====
        # Get which image to show
        img_index = request.args.get('img', 0, type=int)
        if img_index >= len(doc['images']):
            img_index = 0
        image_path = doc['images'][img_index]['path']
        return send_file(image_path)
    
    # ===== HANDLE REGULAR DOCUMENT PREVIEW =====
    file_path = doc['stored_path']
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return "File not found", 404

@bp.route('/document/<doc_id>/download')
def download_document(doc_id):
    """
    Download a document (force download as attachment).
    
    This route forces the browser to download the file instead of displaying it.
    """
    # ===== TRY TO GET AS REGULAR DOCUMENT FIRST =====
    doc = dms.get_document(doc_id)
    
    if not doc:
        # ===== TRY TO GET AS IMAGE GROUP =====
        doc = dms.get_image_group(doc_id)
        if not doc:
            flash('Document not found')
            return redirect(url_for('documents.index'))
        
        # ===== HANDLE IMAGE GROUP DOWNLOAD =====
        img_index = request.args.get('img', 0, type=int)
        if img_index >= len(doc['images']):
            img_index = 0
        image_path = doc['images'][img_index]['path']
        return send_file(image_path, as_attachment=True, 
                        download_name=doc['images'][img_index]['original_name'])
    
    # ===== HANDLE REGULAR DOCUMENT DOWNLOAD =====
    file_path = doc['stored_path']
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=doc['original_name'])
    else:
        flash('File not found')
        return redirect(url_for('documents.index'))

@bp.route('/document/<doc_id>/download-all')
def download_all_images(doc_id):
    """
    Download all images in a group as a ZIP file.
    
    This route creates a temporary ZIP file containing all images in an image group.
    """
    # ===== GET IMAGE GROUP =====
    doc = dms.get_image_group(doc_id)
    if not doc:
        flash('Document not found or not an image group')
        return redirect(url_for('documents.index'))
    
    # ===== CREATE TEMPORARY ZIP FILE =====
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        with zipfile.ZipFile(tmp_file.name, 'w') as zip_file:
            # Add each image to the ZIP file
            for i, image in enumerate(doc['images']):
                if os.path.exists(image['path']):
                    # Create a descriptive filename for each image
                    zip_file.write(image['path'], f"{doc['metadata'].get('name', 'Image Group')}_image_{i+1}.{image.get('file_type', 'jpg')}")
        
        # Serve the ZIP file for download
        return send_file(tmp_file.name, as_attachment=True, 
                        download_name=f"{doc['metadata'].get('name', 'Image Group')}_all_images.zip")

@bp.route('/document/<doc_id>/comment', methods=['POST'])
@login_required
@permission_required('read')
def add_comment(doc_id):
    """
    Add a comment to a document.
    
    This route allows users to add comments to documents they have access to.
    """
    # ===== VALIDATE COMMENT =====
    comment_text = request.form.get('comment', '').strip()
    if not comment_text:
        flash('Comment cannot be empty')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    # ===== ADD COMMENT TO DATABASE =====
    user_id = session.get('username')
    success = dms.add_document_comment(doc_id, user_id, comment_text)
    
    # ===== PROVIDE FEEDBACK =====
    if success:
        flash('Comment added successfully')
    else:
        flash('Failed to add comment')
    
    return redirect(url_for('documents.view_document', doc_id=doc_id))

@bp.route('/document/<doc_id>/version/<version_id>')
@login_required
@permission_required('read')
def view_document_version(doc_id, version_id):
    """
    View a specific version of a document.
    
    This route shows version history for documents (placeholder implementation).
    """
    # ===== GET DOCUMENT =====
    doc = dms.get_document(doc_id)
    
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
    # ===== CREATE PLACEHOLDER VERSION DATA =====
    # For now, return a placeholder version since the method doesn't exist yet
    version = {
        'id': version_id,
        'version_number': version_id,
        'created_at': doc.get('created_at', ''),
        'created_by': doc.get('metadata', {}).get('uploaded_by', 'Unknown'),
        'change_description': 'Version details not available yet'
    }
    
    return render_template('documents/version.html', doc=doc, version=version)

@bp.route('/document/<doc_id>/permissions')
@login_required
def document_permissions(doc_id):
    """
    View document permissions.
    
    This route shows who has access to a document (placeholder implementation).
    """
    # ===== GET DOCUMENT =====
    doc = dms.get_document(doc_id)
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
    # ===== GET USERS FOR DROPDOWN =====
    # Get users for the dropdown (same as admin users route)
    users = Config.USERS
    
    # ===== CREATE PLACEHOLDER PERMISSIONS DATA =====
    # For now, return empty permissions list since the method doesn't exist yet
    permissions = []
    
    return render_template('documents/permissions.html', doc=doc, permissions=permissions, users=users)

@bp.route('/document/<doc_id>/activity')
@login_required
def document_activity(doc_id):
    """
    View document activity log.
    
    This route shows the history of actions performed on a document (placeholder implementation).
    """
    # ===== GET DOCUMENT =====
    doc = dms.get_document(doc_id)
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
    # ===== CREATE PLACEHOLDER ACTIVITY DATA =====
    # For now, return empty activity list since the method doesn't exist yet
    activity = []
    
    return render_template('documents/activity.html', doc=doc, activity=activity)

@bp.route('/set_status/<doc_id>', methods=['POST'])
@login_required
def set_status(doc_id):
    """
    Set document status (admin only).
    
    This route allows admins to change document status between:
    - pending: awaiting approval
    - approved: approved for use
    - rejected: declined/not approved
    """
    # ===== CHECK ADMIN PERMISSIONS =====
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.index'))
    
    # ===== VALIDATE NEW STATUS =====
    new_status = request.form.get('new_status')
    if new_status in ['pending', 'approved', 'rejected']:
        # ===== UPDATE DOCUMENT STATUS =====
        doc = dms.get_document(doc_id)
        if doc:
            # Update the status in the document metadata
            if doc.get('metadata'):
                doc['metadata']['status'] = new_status
            else:
                doc['metadata'] = {'status': new_status}
            
            # Save the updated metadata to the database
            dms.update_metadata(doc_id, doc['metadata'])
            flash(f'Document status updated to {new_status}')
        else:
            flash('Document not found')
    else:
        flash('Invalid status')
    
    # ===== PRESERVE CURRENT FILTER STATE =====
    return redirect(preserve_filters_redirect())

@bp.route('/delete_document/<doc_id>', methods=['POST'])
@login_required
def delete_document(doc_id):
    """
    Delete a document (admin only).
    
    This route performs a soft delete - the document is marked as deleted
    but the file remains in storage for potential recovery.
    """
    # ===== CHECK ADMIN PERMISSIONS =====
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.index'))
    
    # ===== PERFORM SOFT DELETE =====
    success = dms.soft_delete_document(doc_id)
    if success:
        flash('Document deleted successfully')
    else:
        flash('Failed to delete document')
    
    # ===== PRESERVE CURRENT FILTER STATE =====
    return redirect(preserve_filters_redirect()) 

@bp.route('/document/<doc_id>/upload-version', methods=['POST'])
@login_required
@permission_required('write')
def upload_document_version(doc_id):
    """
    Upload a new version of a document.
    
    This route allows users to upload updated versions of existing documents.
    """
    # ===== VALIDATE FILE UPLOAD =====
    if 'document' not in request.files:
        flash('No file selected')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    file = request.files['document']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    # ===== GET CHANGE DESCRIPTION =====
    change_description = request.form.get('change_description', '')
    
    try:
        # ===== SAVE TEMPORARY FILE =====
        temp_path = os.path.join(Config.TEMP_PATH, file.filename)
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        file.save(temp_path)
        
        # ===== ADD VERSION TO DATABASE =====
        success = dms.add_document_version(doc_id, temp_path, change_description, session.get('username'))
        os.remove(temp_path)  # Clean up temporary file
        
        # ===== PROVIDE FEEDBACK =====
        if success:
            flash('New version uploaded successfully')
        else:
            flash('Failed to upload new version')
    except Exception as e:
        flash(f'Error uploading version: {str(e)}')
    
    return redirect(url_for('documents.view_document', doc_id=doc_id))

@bp.route('/document/<doc_id>/update-metadata', methods=['POST'])
@login_required
def update_metadata(doc_id):
    """
    Update document metadata (admin only).
    
    This route allows admins to modify document metadata such as:
    - department
    - tags
    - status
    """
    # ===== CHECK ADMIN PERMISSIONS =====
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    # ===== GET DOCUMENT =====
    doc = dms.get_document(doc_id)
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
    # ===== GET CURRENT METADATA =====
    metadata = doc.get('metadata', {})
    
    # ===== UPDATE METADATA FIELDS =====
    # Update department
    metadata['department'] = request.form.get('department', metadata.get('department', ''))
    
    # Update tags (convert comma-separated string to list)
    metadata['tags'] = request.form.get('tags', '').split(',') if request.form.get('tags') else metadata.get('tags', [])
    
    # Update status
    metadata['status'] = request.form.get('status', metadata.get('status', 'active'))
    
    # ===== SAVE UPDATED METADATA =====
    success = dms.update_metadata(doc_id, metadata)
    
    # ===== PROVIDE FEEDBACK =====
    if success:
        flash('Metadata updated successfully')
    else:
        flash('Failed to update metadata')
    
    return redirect(url_for('documents.view_document', doc_id=doc_id)) 