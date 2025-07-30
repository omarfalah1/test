# هێنانی پێداویستییەکانی فلاسک و سیستەمی فایل
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, session
import os
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.github'))
from index import DocumentManagementSystem
from datetime import datetime
from functools import wraps
from uuid import uuid4

# --- Jinja Filters ---
def format_datetime(value):
    """Format ISO datetime string to 'YYYY-MM-DD HH:MM' beautifully."""
    if not value:
        return ''
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(value)
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(value)

def status_color(value):
    """Return Bootstrap badge color for status."""
    if not value:
        return 'secondary'
    v = value.lower()
    if v == 'pending':
        return 'warning'
    elif v == 'approved':
        return 'success'
    elif v in ['rejected', 'declined']:
        return 'danger'
    return 'secondary'

# دروستکردنی ئەپڵیکەیشنی فلاسک
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # کلیلی نهێنی بۆ پەیامەکان
dms = DocumentManagementSystem()  # دروستکردنی سیستەمی بەڕێوەبردنی دۆکیومێنت

# Register Jinja filters
app.jinja_env.filters['format_datetime'] = format_datetime
app.jinja_env.filters['status_color'] = status_color

# Simple user management: username -> {password, role}
USERS = {
    'admin': {'password': '1111', 'role': 'admin'},
    'employee': {'password': '2222', 'role': 'employee'},
    'omar': {'password': 'omarpass', 'role': 'omar'},
    'pola': {'password': 'polapass', 'role': 'pola'},
}

# دەستکەوتنی پێویستی بۆ هەموو پەڕەکان
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """پەڕەی چوونەژوورەوە"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = USERS.get(username)
        if user and user['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = user['role']
            flash('بەخێربێیت ' + username)
            return redirect(url_for('index'))
        else:
            flash('ناوی بەکارهێنەر یان وشەی نهێنی هەڵەیە')
    return render_template('login.html')

@app.route('/')
@login_required
def index():
    """پیشاندانی پەڕەی سەرەکی لەگەڵ لیستی دۆکیومێنتەکان"""
    role = session.get('role')
    username = session.get('username')

    # Get filter params
    status_filter = request.args.get('status', 'all')
    uploader_filter = request.args.get('uploader', 'all')
    sort_by = request.args.get('sort', 'date_desc')
    search_query = request.args.get('search', '').strip()

    documents = dms.list_documents()
    image_groups = dms.list_image_groups()

    # Gather all uploaders for the filter dropdown
    all_uploaders = sorted(set(
        [doc['metadata'].get('uploaded_by', '') for doc in documents] +
        [g['metadata'].get('uploaded_by', '') for g in image_groups]
    ))

    # Filter function
    def match(meta, name):
        if status_filter != 'all' and meta.get('status') != status_filter:
            return False
        if uploader_filter != 'all' and meta.get('uploaded_by') != uploader_filter:
            return False
        if search_query:
            search_lower = search_query.lower()
            tags = meta.get('tags', [])
            tags_str = ','.join(tags).lower() if isinstance(tags, list) else str(tags).lower()
            if (search_lower not in tags_str and
                search_lower not in str(meta.get('uploaded_by', '')).lower() and
                search_lower not in name.lower()):
                return False
        return True

    # Filter and sort for admin
    if role == 'admin':
        documents = [doc for doc in documents if match(doc['metadata'], doc.get('original_name', ''))]
        image_groups = [g for g in image_groups if match(g['metadata'], g.get('id', ''))]
        reverse = sort_by == 'date_desc'
        documents.sort(key=lambda d: d['metadata'].get('upload_date', d.get('created_at')), reverse=reverse)
        image_groups.sort(key=lambda g: g['metadata'].get('upload_date', g.get('created_at')), reverse=reverse)
        return render_template(
            'index.html',
            documents=documents,
            image_groups=image_groups,
            role=role,
            status_filter=status_filter,
            uploader_filter=uploader_filter,
            sort_by=sort_by,
            search_query=search_query,
            all_uploaders=all_uploaders
        )
    # Filter and sort for employees
    elif role in ['employee', 'omar', 'pola']:
        my_docs = [doc for doc in documents if doc['metadata'].get('uploaded_by') == username]
        my_image_groups = [g for g in image_groups if g['metadata'].get('uploaded_by') == username]
        my_docs = [doc for doc in my_docs if match(doc['metadata'], doc.get('original_name', ''))]
        my_image_groups = [g for g in my_image_groups if match(g['metadata'], g.get('id', ''))]
        reverse = sort_by == 'date_desc'
        my_docs.sort(key=lambda d: d['metadata'].get('upload_date', d.get('created_at')), reverse=reverse)
        my_image_groups.sort(key=lambda g: g['metadata'].get('upload_date', g.get('created_at')), reverse=reverse)
        return render_template(
            'index.html',
            documents=my_docs,
            image_groups=my_image_groups,
            role=role,
            status_filter=status_filter,
            uploader_filter=uploader_filter,
            sort_by=sort_by,
            search_query=search_query,
            all_uploaders=all_uploaders,
            username=username
        )
    else:
        flash('Unauthorized')
        return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    username = session.get('username')

    documents = dms.list_documents()
    image_groups = dms.list_image_groups()

    total_documents = len(documents) + len(image_groups)
    total_image_groups = len(image_groups)

    from datetime import datetime
    now = datetime.now()
    def is_this_month(dtstr):
        try:
            dt = datetime.fromisoformat(dtstr)
            return dt.year == now.year and dt.month == now.month
        except Exception:
            return False
    uploads_this_month = sum(
        is_this_month(doc['metadata'].get('upload_date', doc.get('created_at', '')))
        for doc in documents
    ) + sum(
        is_this_month(g['metadata'].get('upload_date', g.get('created_at', '')))
        for g in image_groups
    )

    from collections import Counter
    status_counter = Counter()
    for doc in documents:
        status = doc['metadata'].get('status', 'unknown')
        status_counter[status] += 1
    for g in image_groups:
        status = g['metadata'].get('status', 'unknown')
        status_counter[status] += 1
    status_counts = dict(status_counter)

    uploads_per_month = [0]*12
    def add_month(dtstr):
        try:
            dt = datetime.fromisoformat(dtstr)
            uploads_per_month[dt.month-1] += 1
        except Exception:
            pass
    for doc in documents:
        add_month(doc['metadata'].get('upload_date', doc.get('created_at', '')))
    for g in image_groups:
        add_month(g['metadata'].get('upload_date', g.get('created_at', '')))

    return render_template(
        'dashboard.html',
        total_documents=total_documents,
        uploads_this_month=uploads_this_month,
        total_image_groups=total_image_groups,
        status_counts=status_counts,
        uploads_per_month=uploads_per_month
    )

@app.route('/logout')
def logout():
    """دەرچوون لە سیستەم"""
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload_document():
    files = request.files.getlist('images')
    if files and any(file.filename for file in files):
        image_infos = []
        for file in files:
            if file and file.filename:
                temp_path = os.path.join('temp', file.filename)
                os.makedirs('temp', exist_ok=True)
                file.save(temp_path)
                stored_name = f"{uuid4()}_{file.filename}"
                stored_path = os.path.join('storage', stored_name)
                os.rename(temp_path, stored_path)
                image_infos.append({
                    'original_name': file.filename,
                    'stored_path': stored_path
                })
        if not image_infos:
            flash('هیچ وێنەیەک دیاری نەکراوە')
            return redirect(url_for('index'))
        role = session.get('role')
        username = session.get('username')
        if role in ['employee', 'omar', 'pola']:
            status = 'pending'
            uploaded_by = username
        else:
            status = request.form.get('status', 'active')
            uploaded_by = request.form.get('uploaded_by', username)
        metadata = {
            'department': request.form.get('department', ''),
            'tags': request.form.get('tags', '').split(','),
            'status': status,
            'uploaded_by': uploaded_by,
            'upload_date': datetime.now().isoformat()
        }
        dms.add_image_group(image_infos, metadata=metadata)
        flash(f'{len(image_infos)} وێنە بە سەرکەوتوویی بارکران!')
        return redirect(url_for('index'))
    # Handle single document (any type)
    if 'document' not in request.files:
        flash('هیچ فایلێک دیاری نەکراوە')
        return redirect(url_for('index'))
    file = request.files['document']
    if file.filename == '':
        flash('هیچ فایلێک دیاری نەکراوە')
        return redirect(url_for('index'))
    try:
        temp_path = os.path.join('temp', file.filename)
        os.makedirs('temp', exist_ok=True)
        file.save(temp_path)
        role = session.get('role')
        username = session.get('username')
        if role in ['employee', 'omar', 'pola']:
            status = 'pending'
            uploaded_by = username
        else:
            status = request.form.get('status', 'active')
            uploaded_by = request.form.get('uploaded_by', username)
        metadata = {
            'department': request.form.get('department', ''),
            'tags': request.form.get('tags', '').split(','),
            'status': status,
            'uploaded_by': uploaded_by,
            'upload_date': datetime.now().isoformat()
        }
        dms.add_document(temp_path, metadata=metadata)
        os.remove(temp_path)
        flash('دۆکیومێنت بە سەرکەوتوویی بارکرا!')
    except Exception as e:
        flash(f'Error uploading document: {str(e)}')
    return redirect(url_for('index'))

@app.route('/document/<doc_id>')
@login_required
def view_document(doc_id):
    """پیشاندانی وردەکارییەکانی دۆکیومێنت یان گرووپی وێنەکان"""
    doc = dms.get_document(doc_id)
    if doc:
        return render_template('document.html', doc=doc)
    # Try as image group
    group = dms.get_image_group(doc_id)
    if group:
        from flask import request
        img_index = int(request.args.get('img', 0))
        if 0 <= img_index < len(group['images']):
            img = group['images'][img_index]
            # Compose a doc-like dict for the template
            doc = {
                'id': group['id'],
                'original_name': img['original_name'],
                'stored_path': img['stored_path'],
                'created_at': group['created_at'],
                'version': 1,
                'metadata': group['metadata'],
                'file_type': 'image',
                'group_images': group['images'],
                'group_img_index': img_index
            }
            return render_template('document.html', doc=doc)
    flash('دۆکیومێنت نەدۆزرایەوە')
    return redirect(url_for('index'))

@app.route('/document/<doc_id>/preview')
def preview_document(doc_id):
    """پێشبینینی ناوەڕۆکی دۆکیومێنت یان گرووپی وێنەکان"""
    doc = dms.get_document(doc_id)
    if doc:
        if doc['file_type'] == 'image':
            return send_file(doc['stored_path'], mimetype=f'image/{os.path.splitext(doc["original_name"])[1][1:]}')
        elif doc['file_type'] == 'text':
            return send_file(doc['stored_path'], mimetype='text/plain')
        else:
            return 'File type not supported for preview', 400
    # Try as image group
    group = dms.get_image_group(doc_id)
    if group:
        from flask import request
        img_index = int(request.args.get('img', 0))
        if 0 <= img_index < len(group['images']):
            img = group['images'][img_index]
            ext = os.path.splitext(img['original_name'])[1][1:]
            return send_file(img['stored_path'], mimetype=f'image/{ext}')
        return 'Image not found in group', 404
    return 'Document not found', 404

@app.route('/document/<doc_id>/download')
def download_document(doc_id):
    """داگرتنی دۆکیومێنت"""
    # وەرگرتنی دۆکیومێنت بۆ داگرتن
    doc = dms.get_document(doc_id)
    if not doc:
        flash('دۆکیومێنت نەدۆزرایەوە')
        return redirect(url_for('index'))
    
    # ناردنی فایلەکە بۆ داگرتن بە ناوی ڕەسەنییەوە
    return send_file(
        doc['stored_path'],
        as_attachment=True,
        download_name=doc['original_name']
    )

@app.route('/document/<doc_id>/delete', methods=['POST'])
def delete_document(doc_id):
    """Archive (soft delete) a document or image group."""
    deleted_by = session.get('username', 'unknown')
    # Try to archive a document
    if dms.archive_document(doc_id, deleted_by=deleted_by):
        flash('دۆکیومێنت بۆ ئەرشیف گواسترایەوە و سڕایەوە')
        return redirect(url_for('index'))
    # Try to archive an image group
    if dms.soft_delete_image_group(doc_id, deleted_by=deleted_by):
        flash('گرووپی وێنەکان بۆ ئەرشیف گواسترایەوە و سڕایەوە')
        return redirect(url_for('index'))
    flash('هەڵە ڕوویدا لە سڕینەوەی دۆکیومێنت')
    return redirect(url_for('index'))

@app.route('/documents/archive', methods=['POST'])
def archive_documents():
    """Archive multiple selected documents."""
    doc_ids = request.form.getlist('doc_ids')
    if not doc_ids:
        flash('هیچ دۆکیومێنتێک هەڵنەبژێردراوە')
        return redirect(url_for('index'))
    deleted_by = session.get('username', 'unknown')
    count = dms.archive_documents(doc_ids, deleted_by=deleted_by)
    flash(f'{count} دۆکیومێنت بۆ ئەرشیف گواستران و سڕانەوە')
    return redirect(url_for('index'))

@app.route('/document/<doc_id>/restore', methods=['POST'])
def restore_document(doc_id):
    """گەڕاندنەوەی دۆکیومێنتی سڕاوە"""
    if dms.restore_document(doc_id):
        flash('Document restored successfully')
    else:
        flash('Error restoring document')
    return redirect(url_for('index'))

@app.route('/document/<doc_id>/metadata', methods=['POST'])
def update_metadata(doc_id):
    """نوێکردنەوەی زانیارییە وەسفییەکانی دۆکیومێنت"""
    # ئامادەکردنی زانیارییە نوێیەکان
    metadata = {
        'department': request.form.get('department', ''),  # بەش
        'tags': request.form.get('tags', '').split(','),  # تاگەکان
        'status': request.form.get('status', ''),         # دۆخ
        'last_modified': datetime.now().isoformat()       # دوایین گۆڕانکاری
    }
    
    # نوێکردنەوەی زانیارییەکان
    if dms.update_metadata(doc_id, metadata):
        flash('زانیارییەکان بە سەرکەوتوویی نوێکرانەوە')
    else:
        flash('هەڵە ڕوویدا لە نوێکردنەوەی زانیارییەکان')
    return redirect(url_for('view_document', doc_id=doc_id))

@app.route('/document/<doc_id>/approve', methods=['POST'])
@login_required
def approve_document(doc_id):
    if session.get('role') != 'admin':
        flash('Unauthorized')
        return redirect(url_for('index'))
    feedback = request.form.get('feedback', '')
    doc = dms.get_document(doc_id)
    meta = doc.get('metadata', {}) if doc else {}
    meta['status'] = 'approved'
    meta['feedback'] = feedback
    meta['last_modified'] = datetime.now().isoformat()
    if dms.update_metadata(doc_id, meta):
        flash('Document approved!')
    else:
        flash('Error approving document')
    return redirect(url_for('index'))

@app.route('/document/<doc_id>/reject', methods=['POST'])
@login_required
def reject_document(doc_id):
    if session.get('role') != 'admin':
        flash('Unauthorized')
        return redirect(url_for('index'))
    feedback = request.form.get('feedback', '')
    doc = dms.get_document(doc_id)
    meta = doc.get('metadata', {}) if doc else {}
    meta['status'] = 'rejected'
    meta['feedback'] = feedback
    meta['last_modified'] = datetime.now().isoformat()
    if dms.update_metadata(doc_id, meta):
        flash('Document rejected!')
    else:
        flash('Error rejecting document')
    return redirect(url_for('index'))

@app.route('/document/<doc_id>/set_status', methods=['POST'])
@login_required
def set_status(doc_id):
    if session.get('role') != 'admin':
        flash('Unauthorized')
        return redirect(url_for('index'))
    new_status = request.form.get('new_status')
    if new_status not in ['approved', 'rejected', 'pending']:
        flash('Invalid status')
        return redirect(url_for('index'))
    doc = dms.get_document(doc_id)
    if doc:
        meta = doc.get('metadata', {})
        meta['status'] = new_status
        meta['last_modified'] = datetime.now().isoformat()
        if dms.update_metadata(doc_id, meta):
            flash(f'Status changed to {new_status}!')
        else:
            flash('Error changing status')
        return redirect(url_for('index'))
    # Try as image group
    group = dms.get_image_group(doc_id)
    if group:
        meta = group['metadata']
        meta['status'] = new_status
        meta['last_modified'] = datetime.now().isoformat()
        import json
        with dms.get_db_connection() as conn:
            conn.execute("UPDATE image_groups SET metadata = ? WHERE id = ?", (json.dumps(meta), doc_id))
        flash(f'Status changed to {new_status}!')
        return redirect(url_for('index'))
    flash('Error changing status')
    return redirect(url_for('index'))

@app.route('/admin/fix_employee_uploaded_by')
@login_required
def fix_employee_uploaded_by():
    if session.get('role') != 'admin':
        flash('Unauthorized')
        return redirect(url_for('index'))
    count = 0
    docs = dms.list_documents(include_deleted=True)
    for doc in docs:
        meta = doc.get('metadata', {})
        uploaded_by = meta.get('uploaded_by', '')
        # Fix if uploaded_by is empty or not a known user
        if not uploaded_by or uploaded_by.lower() not in ['admin', 'employee']:
            meta['uploaded_by'] = 'employee'
            dms.update_metadata(doc['id'], meta)
            count += 1
    flash(f'Fixed {count} documents. Now all employee docs have correct uploaded_by.')
    return redirect(url_for('index'))

@app.route('/document/<doc_id>/permanent_delete', methods=['POST'])
@login_required
def permanent_delete_document(doc_id):
    if session.get('role') != 'admin':
        flash('Unauthorized')
        return redirect(url_for('index'))
    try:
        if dms.remove_document_permanently(doc_id):
            flash('Document permanently deleted!')
        else:
            flash('Document not found or already deleted.')
    except Exception as e:
        flash(f'Error deleting document: {str(e)}')
    return redirect(url_for('index'))

@app.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    if session.get('role') != 'admin':
        flash('Unauthorized')
        return redirect(url_for('index'))
    global USERS
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        if action == 'add':
            password = request.form.get('password')
            role = request.form.get('role')
            if username in USERS:
                flash('Username already exists')
            else:
                USERS[username] = {'password': password, 'role': role}
                flash('User added successfully')
        elif action == 'remove':
            if username in USERS and username != 'admin':
                USERS.pop(username)
                flash('User removed successfully')
            else:
                flash('Cannot remove admin user')
    return render_template('users.html', users=USERS)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
