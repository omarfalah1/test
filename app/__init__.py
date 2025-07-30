"""
Document Management System - Flask Application
"""

from flask import Flask
from app.config import Config
from app.utils.helpers import register_filters
from app.utils.decorators import register_decorators

def create_app(config_class=Config):
    """Application factory pattern for creating Flask app."""
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)
    
    # Register Jinja filters
    register_filters(app)
    
    # Register decorators
    register_decorators(app)
    
    # Register blueprints
    from app.routes import auth, documents, search, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(admin.bp)
    
    return app 