"""
Document management routes
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file, session
from app.models.document_manager import DocumentManagementSystem
from app.utils.decorators import login_required, permission_required
from app.config import Config
import os
import zipfile
import tempfile
from datetime import datetime, timedelta
from uuid import uuid4

bp = Blueprint('documents', __name__)
dms = DocumentManagementSystem()

@bp.route('/')
@login_required
def index():
    """Main documents page."""
    documents = dms.list_documents()
    image_groups = dms.list_image_groups()
    
    # Filter documents based on user role and ownership/sharing
    current_user = session.get('username')
    current_role = session.get('role')
    
    if current_role != 'admin':
        # Non-admin users can only see documents they uploaded or were sent to them
        filtered_documents = []
        for doc in documents:
            doc_uploader = doc.get('metadata', {}).get('uploaded_by', '')
            doc_recipients = doc.get('metadata', {}).get('recipients', [])
            
            # User can see if they uploaded it or if they're in the recipients list
            if doc_uploader == current_user or current_user in doc_recipients:
                filtered_documents.append(doc)
        
        documents = filtered_documents
        
        # Filter image groups similarly
        filtered_image_groups = []
        for group in image_groups:
            group_uploader = group.get('metadata', {}).get('uploaded_by', '')
            group_recipients = group.get('metadata', {}).get('recipients', [])
            
            # User can see if they uploaded it or if they're in the recipients list
            if group_uploader == current_user or current_user in group_recipients:
                filtered_image_groups.append(group)
        
        image_groups = filtered_image_groups
    
    # Get filter parameters
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')
    uploader_filter = request.args.get('uploader', 'all')
    sort_by = request.args.get('sort', 'date_desc')
    
    # Get all unique uploaders for filter dropdown
    all_uploaders = set()
    for doc in documents:
        if doc.get('metadata', {}).get('uploaded_by'):
            all_uploaders.add(doc['metadata']['uploaded_by'])
    for group in image_groups:
        if group.get('metadata', {}).get('uploaded_by'):
            all_uploaders.add(group['metadata']['uploaded_by'])
    all_uploaders = sorted(list(all_uploaders))
    
    # Apply filters to regular documents
    if search_query:
        documents = [doc for doc in documents if search_query.lower() in doc.get('original_name', '').lower()]
    
    if status_filter != 'all':
        documents = [doc for doc in documents if doc.get('metadata', {}).get('status') == status_filter]
    
    if uploader_filter != 'all':
        documents = [doc for doc in documents if doc.get('metadata', {}).get('uploaded_by') == uploader_filter]
    
    # Apply filters to image groups
    if search_query:
        filtered_image_groups = []
        for group in image_groups:
            group_name = group.get('metadata', {}).get('name', '').lower()
            group_tags = ' '.join(group.get('metadata', {}).get('tags', [])).lower()
            if (search_query.lower() in group_name or 
                search_query.lower() in group_tags):
                filtered_image_groups.append(group)
        image_groups = filtered_image_groups
    
    if status_filter != 'all':
        image_groups = [group for group in image_groups if group.get('metadata', {}).get('status') == status_filter]
    
    if uploader_filter != 'all':
        image_groups = [group for group in image_groups if group.get('metadata', {}).get('uploaded_by') == uploader_filter]
    
    # Apply sorting
    if sort_by == 'date_asc':
        documents.sort(key=lambda x: x.get('created_at', ''))
        image_groups.sort(key=lambda x: x.get('created_at', ''))
    elif sort_by == 'date_desc':
        documents.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        image_groups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    elif sort_by == 'uploader':
        documents.sort(key=lambda x: x.get('metadata', {}).get('uploaded_by', ''))
        image_groups.sort(key=lambda x: x.get('metadata', {}).get('uploaded_by', ''))
    elif sort_by == 'status':
        documents.sort(key=lambda x: x.get('metadata', {}).get('status', ''))
        image_groups.sort(key=lambda x: x.get('metadata', {}).get('status', ''))
    
    # Group documents by type
    regular_docs = [doc for doc in documents if not doc.get('group_images')]
    
    # Add some sample data if no documents exist (for testing)
    if not documents and not image_groups:
        # Create a sample document for testing
        sample_metadata = {
            'department': 'IT',
            'tags': ['sample', 'test'],
            'status': 'active',
            'uploaded_by': session.get('username', 'admin'),
            'upload_date': datetime.now().isoformat()
        }
        
        # Create a sample text file
        sample_file_path = os.path.join(Config.TEMP_PATH, 'sample_document.txt')
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        with open(sample_file_path, 'w') as f:
            f.write('This is a sample document for testing the DMS system.')
        
        try:
            dms.add_document(sample_file_path, metadata=sample_metadata, created_by=session.get('username', 'admin'))
            os.remove(sample_file_path)
            flash('Sample document created for testing!')
            # Refresh the documents list
            documents = dms.list_documents()
            regular_docs = [doc for doc in documents if not doc.get('group_images')]
            image_groups = dms.list_image_groups()
        except Exception as e:
            flash(f'Error creating sample document: {str(e)}')
    
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
    """Upload a document or image group."""
    files = request.files.getlist('images')
    if files and any(file.filename for file in files):
        image_infos = []
        for file in files:
            if file and file.filename:
                temp_path = os.path.join(Config.TEMP_PATH, file.filename)
                os.makedirs(Config.TEMP_PATH, exist_ok=True)
                file.save(temp_path)
                stored_name = f"{uuid4()}_{file.filename}"
                stored_path = os.path.join(Config.STORAGE_PATH, stored_name)
                os.rename(temp_path, stored_path)
                image_infos.append({
                    'original_name': file.filename,
                    'stored_path': stored_path,
                    'filename': stored_name,
                    'path': stored_path
                })
        if not image_infos:
            flash('No images selected')
            return redirect(url_for('documents.index'))
        role = session.get('role')
        username = session.get('username')
        if role in ['employee', 'omar', 'pola']:
            status = 'pending'
            uploaded_by = username
        else:
            status = request.form.get('status', 'active')
            uploaded_by = request.form.get('uploaded_by', username)
        # Get recipients
        recipients = request.form.getlist('recipients')
        
        metadata = {
            'department': request.form.get('department', ''),
            'tags': request.form.get('tags', '').split(','),
            'status': status,
            'uploaded_by': uploaded_by,
            'upload_date': datetime.now().isoformat(),
            'recipients': recipients
        }
        dms.add_image_group(image_infos, metadata=metadata)
        flash(f'{len(image_infos)} images uploaded successfully!')
        return redirect(url_for('documents.index'))
    
    # Handle single document (any type)
    if 'document' not in request.files:
        flash('No file selected')
        return redirect(url_for('documents.index'))
    file = request.files['document']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('documents.index'))
    try:
        temp_path = os.path.join(Config.TEMP_PATH, file.filename)
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        file.save(temp_path)
        role = session.get('role')
        username = session.get('username')
        if role in ['employee', 'omar', 'pola']:
            status = 'pending'
            uploaded_by = username
        else:
            status = request.form.get('status', 'active')
            uploaded_by = request.form.get('uploaded_by', username)
        # Get recipients
        recipients = request.form.getlist('recipients')
        
        metadata = {
            'department': request.form.get('department', ''),
            'tags': request.form.get('tags', '').split(','),
            'status': status,
            'uploaded_by': uploaded_by,
            'upload_date': datetime.now().isoformat(),
            'recipients': recipients
        }
        dms.add_document(temp_path, metadata=metadata, created_by=username)
        os.remove(temp_path)
        flash('Document uploaded successfully!')
    except Exception as e:
        flash(f'Error uploading document: {str(e)}')
    return redirect(url_for('documents.index'))

@bp.route('/document/<doc_id>')
@login_required
@permission_required('read')
def view_document(doc_id):
    """View a specific document."""
    # First try to get as regular document
    doc = dms.get_document(doc_id)
    
    if not doc:
        # Try to get as image group
        doc = dms.get_image_group(doc_id)
        if not doc:
            flash('Document not found')
            return redirect(url_for('documents.index'))
        
        # Handle image groups
        img_index = request.args.get('img', 0, type=int)
        if img_index >= len(doc['images']):
            img_index = 0
        
        # Create a document-like structure for the current image
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
            'group_images': doc['images'],
            'current_image_index': img_index,
            'current_image': current_image,
            'metadata': doc['metadata']  # Include the original metadata
        }
    
    # Get comments for the document
    comments = dms.get_document_comments(doc_id)
    
    return render_template('documents/view.html', doc=doc, comments=comments)

@bp.route('/document/<doc_id>/preview')
def preview_document(doc_id):
    """Preview a document."""
    # First try to get as regular document
    doc = dms.get_document(doc_id)
    
    if not doc:
        # Try to get as image group
        doc = dms.get_image_group(doc_id)
        if not doc:
            return "Document not found", 404
        
        # Handle image groups
        img_index = request.args.get('img', 0, type=int)
        if img_index >= len(doc['images']):
            img_index = 0
        image_path = doc['images'][img_index]['path']
        return send_file(image_path)
    
    # Handle regular documents
    file_path = doc['stored_path']
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return "File not found", 404

@bp.route('/document/<doc_id>/download')
def download_document(doc_id):
    """Download a document."""
    # First try to get as regular document
    doc = dms.get_document(doc_id)
    
    if not doc:
        # Try to get as image group
        doc = dms.get_image_group(doc_id)
        if not doc:
            flash('Document not found')
            return redirect(url_for('documents.index'))
        
        # Handle image groups
        img_index = request.args.get('img', 0, type=int)
        if img_index >= len(doc['images']):
            img_index = 0
        image_path = doc['images'][img_index]['path']
        return send_file(image_path, as_attachment=True, 
                        download_name=doc['images'][img_index]['original_name'])
    
    # Handle regular documents
    file_path = doc['stored_path']
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=doc['original_name'])
    else:
        flash('File not found')
        return redirect(url_for('documents.index'))

@bp.route('/document/<doc_id>/download-all')
def download_all_images(doc_id):
    """Download all images in a group as ZIP."""
    # Try to get as image group
    doc = dms.get_image_group(doc_id)
    if not doc:
        flash('Document not found or not an image group')
        return redirect(url_for('documents.index'))
    
    # Create a temporary ZIP file
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        with zipfile.ZipFile(tmp_file.name, 'w') as zip_file:
            for i, image in enumerate(doc['images']):
                if os.path.exists(image['path']):
                    zip_file.write(image['path'], f"{doc['metadata'].get('name', 'Image Group')}_image_{i+1}.{image.get('file_type', 'jpg')}")
        
        return send_file(tmp_file.name, as_attachment=True, 
                        download_name=f"{doc['metadata'].get('name', 'Image Group')}_all_images.zip")

@bp.route('/document/<doc_id>/comment', methods=['POST'])
@login_required
@permission_required('read')
def add_comment(doc_id):
    """Add a comment to a document."""
    comment_text = request.form.get('comment', '').strip()
    if not comment_text:
        flash('Comment cannot be empty')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    user_id = session.get('username')
    success = dms.add_document_comment(doc_id, user_id, comment_text)
    
    if success:
        flash('Comment added successfully')
    else:
        flash('Failed to add comment')
    
    return redirect(url_for('documents.view_document', doc_id=doc_id))

@bp.route('/document/<doc_id>/version/<version_id>')
@login_required
@permission_required('read')
def view_document_version(doc_id, version_id):
    """View a specific version of a document."""
    doc = dms.get_document(doc_id)
    
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
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
    """View document permissions."""
    doc = dms.get_document(doc_id)
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
    # Get users for the dropdown (same as admin users route)
    users = Config.USERS
    
    # For now, return empty permissions list since the method doesn't exist yet
    permissions = []
    
    return render_template('documents/permissions.html', doc=doc, permissions=permissions, users=users)

@bp.route('/document/<doc_id>/activity')
@login_required
def document_activity(doc_id):
    """View document activity log."""
    doc = dms.get_document(doc_id)
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
    # For now, return empty activity list since the method doesn't exist yet
    activity = []
    
    return render_template('documents/activity.html', doc=doc, activity=activity)

@bp.route('/set_status/<doc_id>', methods=['POST'])
@login_required
def set_status(doc_id):
    """Set document status (admin only)."""
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.index'))
    
    new_status = request.form.get('new_status')
    if new_status in ['pending', 'approved', 'rejected']:
        # Update document status
        doc = dms.get_document(doc_id)
        if doc:
            if doc.get('metadata'):
                doc['metadata']['status'] = new_status
            else:
                doc['metadata'] = {'status': new_status}
            
            # Update in database
            dms.update_metadata(doc_id, doc['metadata'])
            flash(f'Document status updated to {new_status}')
        else:
            flash('Document not found')
    else:
        flash('Invalid status')
    
    return redirect(url_for('documents.index'))

@bp.route('/delete_document/<doc_id>', methods=['POST'])
@login_required
def delete_document(doc_id):
    """Delete a document (admin only)."""
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.index'))
    
    success = dms.soft_delete_document(doc_id)
    if success:
        flash('Document deleted successfully')
    else:
        flash('Failed to delete document')
    
    return redirect(url_for('documents.index')) 

@bp.route('/document/<doc_id>/upload-version', methods=['POST'])
@login_required
@permission_required('write')
def upload_document_version(doc_id):
    """Upload a new version of a document."""
    if 'document' not in request.files:
        flash('No file selected')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    file = request.files['document']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    change_description = request.form.get('change_description', '')
    
    try:
        temp_path = os.path.join(Config.TEMP_PATH, file.filename)
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        file.save(temp_path)
        
        success = dms.add_document_version(doc_id, temp_path, change_description, session.get('username'))
        os.remove(temp_path)
        
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
    """Update document metadata (admin only)."""
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    doc = dms.get_document(doc_id)
    if not doc:
        flash('Document not found')
        return redirect(url_for('documents.index'))
    
    # Get current metadata
    metadata = doc.get('metadata', {})
    
    # Update metadata fields
    metadata['department'] = request.form.get('department', metadata.get('department', ''))
    metadata['tags'] = request.form.get('tags', '').split(',') if request.form.get('tags') else metadata.get('tags', [])
    metadata['status'] = request.form.get('status', metadata.get('status', 'active'))
    
    # Update in database
    success = dms.update_metadata(doc_id, metadata)
    
    if success:
        flash('Metadata updated successfully')
    else:
        flash('Failed to update metadata')
    
    return redirect(url_for('documents.view_document', doc_id=doc_id)) 