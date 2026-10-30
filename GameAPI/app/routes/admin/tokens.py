"""
Routes for managing API tokens.
"""

from flask import Blueprint, jsonify, request, render_template, redirect, url_for
from app.models import Token
from app import db
from flask_login import login_required

bp = Blueprint('tokens', __name__)

@bp.route('/admin/api/tokens', methods=['GET'])
def get_tokens():
    """Fetch all tokens."""
    tokens = Token.query.all()
    return jsonify([token.to_dict() for token in tokens])

@bp.route('/admin/api/tokens', methods=['POST'])
def create_token():
    """Create a new token."""
    data = request.get_json()
    token = Token(
        account_id=data['account_id'],
        token=data['token'],
        valid_until=data['valid_until']
    )
    db.session.add(token)
    db.session.commit()
    return jsonify(token.to_dict()), 201

@bp.route('/tokens', methods=['GET', 'POST'])
@login_required
def manage_tokens():
    if request.method == 'POST':
        account_id = request.form['account_id']
        token = request.form['token']
        valid_until = request.form['valid_until']
        token = Token(account_id=account_id, token=token, valid_until=valid_until)
        db.session.add(token)
        db.session.commit()
        return redirect(url_for('tokens.manage_tokens'))
    tokens = Token.query.all()
    return render_template('admin/tokens.html', tokens=tokens)