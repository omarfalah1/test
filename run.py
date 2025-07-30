#!/usr/bin/env python3
"""
Document Management System - Main Entry Point
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 