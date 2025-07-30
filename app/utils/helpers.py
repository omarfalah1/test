"""
Helper functions and Jinja filters
"""

from datetime import datetime

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

def format_file_size(size_bytes):
    """Format file size in human readable format."""
    if size_bytes is None or size_bytes == '':
        return "Unknown"
    try:
        size_bytes = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    except (ValueError, TypeError):
        return "Unknown"

def register_filters(app):
    """Register Jinja filters with the Flask app."""
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.jinja_env.filters['status_color'] = status_color
    app.jinja_env.filters['format_file_size'] = format_file_size 