"""
Configuration settings for the Document Management System
"""

import os

class Config:
    """Base configuration class."""
    SECRET_KEY = 'your-secret-key-here'
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'dms_metadata.db')
    STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage')
    ARCHIVE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'archive')
    TEMP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
    
    # User management
    USERS = {
        'admin': {'password': '1111', 'role': 'admin'},
        'mqwrya': {'password': 'mqwryapass', 'role': 'admin'},
        'employee': {'password': '2222', 'role': 'employee'},
        'omar': {'password': 'omarpass', 'role': 'omar'},
        'pola': {'password': 'polapass', 'role': 'pola'},
    } 