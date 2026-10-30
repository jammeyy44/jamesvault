"""
Routes for managing API logs.
"""

from flask import Blueprint, jsonify, request, render_template
from app.models import APILog
from app import db
from flask_login import login_required

bp = Blueprint('logs', __name__)

@bp.route('/admin/api/logs', methods=['GET'])
def get_logs():
    """Fetch all API logs."""
    logs = APILog.query.all()
    return jsonify([log.to_dict() for log in logs])


@bp.route('/logs')
@login_required
def view_logs():
    logs = APILog.query.all()
    return render_template('admin/logs.html', logs=logs)