"""
Authentication routes
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.config import Config

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in Config.USERS and Config.USERS[username]['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = Config.USERS[username]['role']
            flash('Login successful!')
            return redirect(url_for('documents.index'))
        else:
            flash('Invalid username or password')
    
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    """User logout route."""
    session.clear()
    flash('You have been logged out')
    return redirect(url_for('auth.login')) 