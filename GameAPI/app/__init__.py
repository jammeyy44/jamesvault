"""
Flask application initialization module.

This module sets up the Flask application with all necessary extensions,
security configurations, and route registrations following best practices.
"""

import logging
import json
from typing import Optional
from flask import Flask, request, render_template, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin
from flask_cors import CORS
from flask_restx import Api
from flask_swagger_ui import get_swaggerui_blueprint
from flask_caching import Cache
from flask_login import login_required
from config import Config

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
cache = Cache()

@login_manager.user_loader
def load_user(user_id):
    from app.models import Admin
    return db.session.get(Admin, int(user_id))

class AnonymousUser(UserMixin):
    """Allows unauthenticated users to access routes without triggering login."""
    @property
    def is_authenticated(self):
        return False

login_manager.anonymous_user = AnonymousUser
login_manager.login_view = 'auth.login'

# Custom Jinja2 filter for pretty JSON
def tojson_pretty(value):
    return json.dumps(value, indent=2, ensure_ascii=False)
app.jinja_env.filters['tojson_pretty'] = tojson_pretty

@app.before_request
def bypass_login_for_swagger():
    """Disable authentication for Swagger UI."""
    if request.path.startswith("/swagger"):
        request._login_disabled = True  # Disable authentication for this request

# Swagger UI configuration
SWAGGER_URL = '/swagger'  # URL for accessing Swagger UI
API_URL = '/swagger.json'  # URL for the API specification

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': 'Game Provider API'
    }
)

# Initialize Flask-RESTX API
api = Api(
    version='1.0',
    title='Game Provider API',
    description='A Centralized API for third-party game providers.',
    doc='/swagger/'
)

# Import and register blueprints
from app.routes.admin.auth import bp as auth_bp
from app.routes.admin.dashboard import bp as dashboard_bp

app.register_blueprint(auth_bp, url_prefix='/admin')
app.register_blueprint(dashboard_bp, url_prefix='/admin')

# Import models
from app import models

# Define admin dashboard route
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

def create_app(config_class: type = Config) -> Flask:
    """
    Factory function to create and configure the Flask application.

    This function follows the application factory pattern for better
    testability and configuration management.

    Args:
        config_class: Configuration class to use (defaults to Config).

    Returns:
        Configured Flask application instance.

    Example:
        >>> app = create_app(Config)
        >>> app.run()
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions with the app
    db.init_app(app)
    cache.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # CORS: the Next.js app proxies /api/* (same origin), so cross-origin access is off unless CORS_ORIGINS is set.
    origins = app.config.get('CORS_ORIGINS') or []
    if origins:
        CORS(
            app,
            resources={r"/api/*": {"origins": origins}},
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
            supports_credentials=True,
        )

    # Security headers middleware
    @app.after_request
    def set_security_headers(response):
        """Add security headers to all responses."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if request.path.startswith('/api/v1'):
            response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        return response

    # Request logging
    @app.before_request
    def log_request_info():
        """Log request information for debugging and monitoring."""
        logger.info(
            f"Request: {request.method} {request.path} "
            f"from {request.remote_addr}"
        )

    # Import models to ensure they are registered
    from app import models

    # Import and add namespaces
    from app.routes.api.category1 import category1_ns
    from app.routes.api.category2 import category2_ns
    from app.routes.api.category3 import category3_ns
    from app.routes.api.category4 import category4_ns
    from app.routes.api.category5 import category5_ns
    from app.routes.api.vblink import vblink_ns
    
    api.add_namespace(category1_ns)
    api.add_namespace(category2_ns)
    api.add_namespace(category3_ns)
    api.add_namespace(category4_ns)
    api.add_namespace(category5_ns)
    api.add_namespace(vblink_ns)
    api.init_app(app)

    from app.routes.site import site_bp
    app.register_blueprint(site_bp)
    from app.routes.webhooks import hooks_bp
    app.register_blueprint(hooks_bp)
    from app.routes.uploads import uploads_bp
    app.register_blueprint(uploads_bp)

    # The admin panel is part of the Next.js site (/admin); staff sign in with the normal player login.

    # Register Swagger UI blueprint
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return {'error': 'Resource not found'}, 404

    from sqlalchemy.exc import OperationalError

    @app.errorhandler(OperationalError)
    def database_unavailable(error):
        """The database could not be reached (wrong URL, IPv6-only host, paused project, network). Log the driver's
        reason (never the URL, which contains the password) and answer with a clear, retryable 503."""
        db.session.rollback()
        logger.error("Database unavailable: %s", type(error.orig).__name__ if error.orig else "OperationalError")
        return {'error': 'The service is temporarily unavailable. Please try again shortly.',
                'code': 'database_unavailable'}, 503

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {error}")
        return {'error': 'Internal server error'}, 500

    logger.info("Flask application created successfully")
    return app

# Create the app
app = create_app()

# Verify cache initialization
with app.app_context():
    try:
        cache.set("test_key", "test_value", timeout=60)
        test_value = cache.get("test_key")
        if test_value:
            logger.info("Cache initialized successfully")
        else:
            logger.warning("Cache test failed - check Redis connection")
    except Exception as e:
        logger.error(f"Cache initialization error: {e}")