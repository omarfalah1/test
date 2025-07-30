"""
Search routes
"""

from flask import Blueprint, render_template, request, jsonify, session
from app.models.document_manager import DocumentManagementSystem
from app.utils.decorators import login_required

bp = Blueprint('search', __name__)
dms = DocumentManagementSystem()

@bp.route('/advanced-search')
@login_required
def advanced_search():
    """Advanced search page."""
    # Get search parameters
    query = request.args.get('q', '')
    file_type = request.args.get('file_type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    size_min = request.args.get('size_min', '')
    size_max = request.args.get('size_max', '')
    status = request.args.get('status', '')
    
    # Perform search if parameters are provided
    results = []
    if query or file_type or date_from or date_to or size_min or size_max or status:
        filters = {}
        if file_type:
            filters['file_type'] = file_type
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        if size_min:
            filters['size_min'] = size_min
        if size_max:
            filters['size_max'] = size_max
        if status:
            filters['status'] = status
        
        results = dms.advanced_search(
            query=query,
            filters=filters
        )
    
    # Get saved searches
    saved_searches = dms.get_saved_searches(session.get('username', ''))
    
    # Create filters object for template
    filters = {
        'query': query,
        'file_type': file_type,
        'date_range': [date_from, date_to] if date_from or date_to else None,
        'file_size_min': int(size_min) * 1024 if size_min else None,
        'file_size_max': int(size_max) * 1024 if size_max else None,
        'status': status
    }
    
    return render_template('search/advanced.html', 
                         results=results,
                         saved_searches=saved_searches,
                         filters=filters)

@bp.route('/save-search', methods=['POST'])
@login_required
def save_search():
    """Save a search query."""
    search_name = request.form.get('search_name', '').strip()
    search_query = request.form.get('search_query', '').strip()
    
    if not search_name or not search_query:
        return jsonify({'success': False, 'message': 'Search name and query are required'})
    
    user_id = session.get('username')
    success = dms.save_search(user_id, search_name, search_query)
    
    if success:
        return jsonify({'success': True, 'message': 'Search saved successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to save search'}) 