"""
Authentication and permission decorators
"""

from functools import wraps
from flask import session, redirect, url_for, flash
from app.models.document_manager import DocumentManagementSystem

# Initialize DMS instance
dms = DocumentManagementSystem()

def login_required(f):
    """Decorator to require user login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_type='read'):
    """Decorator to check document permissions."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('auth.login'))
            
            # Admin has all permissions
            if session.get('role') == 'admin':
                return f(*args, **kwargs)
            
            # Check document-specific permissions
            doc_id = kwargs.get('doc_id')
            if doc_id:
                user_id = session.get('username')
                if not dms.check_user_permission(doc_id, user_id, permission_type):
                    flash('You do not have permission to perform this action')
                    return redirect(url_for('documents.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def register_decorators(app):
    """Register decorators with the Flask app."""
    # Decorators are already defined as functions, no additional registration needed
    pass 