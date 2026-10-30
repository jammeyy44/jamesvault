"""
Initialization file for admin routes.
"""

from flask import Blueprint, render_template
from .auth import bp as auth_bp
from .accounts import bp as accounts_bp
from .tokens import bp as tokens_bp
from .logs import bp as logs_bp
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView


# Create a Blueprint for the admin dashboard
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin_dashboard():
    """Render the admin dashboard."""
    admin = Admin(app, name='Admin Dashboard', template_mode='bootstrap3')
    # Example: admin.add_view(ModelView(Store, db.session))

    return admin

# Register all admin routes
admin_bp.register_blueprint(auth_bp, url_prefix='/admin/api')
admin_bp.register_blueprint(accounts_bp, url_prefix='/admin/api')
admin_bp.register_blueprint(tokens_bp, url_prefix='/admin/api')
admin_bp.register_blueprint(logs_bp, url_prefix='/admin/api')