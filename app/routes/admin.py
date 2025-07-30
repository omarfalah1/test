"""
Admin routes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models.document_manager import DocumentManagementSystem
from app.utils.decorators import login_required
from app.config import Config

bp = Blueprint('admin', __name__)
dms = DocumentManagementSystem()

@bp.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard."""
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.index'))
    
    # Get all documents and image groups (same as documents screen)
    documents = dms.list_documents()
    image_groups = dms.list_image_groups()
    
    # Group documents by type (same as documents screen)
    regular_docs = [doc for doc in documents if not doc.get('group_images')]
    
    # Calculate statistics from regular documents
    total_regular_docs = len(regular_docs)
    pending_regular_docs = len([d for d in regular_docs if d.get('metadata', {}).get('status') == 'pending'])
    approved_regular_docs = len([d for d in regular_docs if d.get('metadata', {}).get('status') == 'approved'])
    rejected_regular_docs = len([d for d in regular_docs if d.get('metadata', {}).get('status') == 'rejected'])
    
    # Calculate statistics from image groups
    total_image_groups = len(image_groups)
    pending_image_groups = len([g for g in image_groups if g.get('metadata', {}).get('status') == 'pending'])
    approved_image_groups = len([g for g in image_groups if g.get('metadata', {}).get('status') == 'approved'])
    rejected_image_groups = len([g for g in image_groups if g.get('metadata', {}).get('status') == 'rejected'])
    
    # Combined totals
    total_docs = total_regular_docs + total_image_groups
    pending_docs = pending_regular_docs + pending_image_groups
    approved_docs = approved_regular_docs + approved_image_groups
    rejected_docs = rejected_regular_docs + rejected_image_groups
    
    # Monthly upload statistics (combine regular docs and image groups)
    monthly_stats = {}
    
    # Process regular documents
    for doc in regular_docs:
        upload_date = doc.get('metadata', {}).get('upload_date') or doc.get('created_at')
        if upload_date:
            try:
                month = upload_date[:7]  # YYYY-MM
                monthly_stats[month] = monthly_stats.get(month, 0) + 1
            except:
                pass
    
    # Process image groups
    for group in image_groups:
        upload_date = group.get('metadata', {}).get('upload_date') or group.get('created_at')
        if upload_date:
            try:
                month = upload_date[:7]  # YYYY-MM
                monthly_stats[month] = monthly_stats.get(month, 0) + 1
            except:
                pass
    
    # Sort months
    sorted_months = sorted(monthly_stats.keys())
    monthly_data = [monthly_stats.get(month, 0) for month in sorted_months]
    
    # Create status counts for chart
    status_counts = {
        'pending': pending_docs,
        'approved': approved_docs,
        'rejected': rejected_docs
    }
    
    # Create monthly uploads data for chart (12 months)
    uploads_per_month = [0] * 12  # Initialize with zeros for all months
    for i, month in enumerate(sorted_months):
        if i < 12:  # Ensure we don't exceed 12 months
            try:
                month_num = int(month.split('-')[1]) - 1  # Convert MM to 0-based index
                uploads_per_month[month_num] = monthly_data[i]
            except:
                pass
    
    return render_template('admin/dashboard.html',
                         total_documents=total_docs,
                         total_regular_docs=total_regular_docs,
                         total_image_groups=total_image_groups,
                         uploads_this_month=monthly_data[-1] if monthly_data else 0,
                         status_counts=status_counts,
                         uploads_per_month=uploads_per_month,
                         # Detailed breakdown for debugging
                         pending_regular=pending_regular_docs,
                         approved_regular=approved_regular_docs,
                         rejected_regular=rejected_regular_docs,
                         pending_images=pending_image_groups,
                         approved_images=approved_image_groups,
                         rejected_images=rejected_image_groups)

@bp.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    """User management."""
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('documents.index'))
    
    if request.method == 'POST':
        # Handle user management actions
        action = request.form.get('action')
        username = request.form.get('username')
        
        if action == 'add_user':
            password = request.form.get('password')
            role = request.form.get('role')
            # Add user logic here
            flash('User added successfully')
        elif action == 'delete_user':
            # Delete user logic here
            flash('User deleted successfully')
    
    # Get all users
    users = list(Config.USERS.items())
    
    return render_template('admin/users.html', users=users) 