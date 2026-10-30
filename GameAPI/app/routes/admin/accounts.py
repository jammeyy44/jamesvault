"""
Routes for managing admin accounts.
"""

from flask import Blueprint, jsonify, request, render_template, redirect, url_for
from flask_login import login_required
from app.models import Account
from app import db

bp = Blueprint('accounts', __name__)

@bp.route('/admin/api/accounts', methods=['GET'])
def get_accounts():
    """Fetch all accounts."""
    accounts = Account.query.all()
    return jsonify([account.to_dict() for account in accounts])

@bp.route('/admin/api/accounts', methods=['POST'])
def create_account():
    """Create a new account."""
    data = request.get_json()
    account = Account(
        username=data['username'],
        email=data['email'],
        password=data['password']
    )
    db.session.add(account)
    db.session.commit()
    return jsonify(account.to_dict()), 201

@bp.route('/accounts', methods=['GET', 'POST'])
@login_required
def manage_accounts():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        account = Account(username=username, email=email, password=password)
        db.session.add(account)
        db.session.commit()
        return redirect(url_for('accounts.manage_accounts'))
    accounts = Account.query.all()
    return render_template('admin/accounts.html', accounts=accounts)