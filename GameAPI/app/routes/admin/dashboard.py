# app/routes/admin/dashboard.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Provider
import requests
from app import app

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
@login_required
def dashboard():
    providers = Provider.query.all()
    return render_template('admin/dashboard.html', providers=providers)

@bp.route('/provider/manage/<int:provider_id>', methods=['GET', 'POST'])
@login_required
def manage_provider(provider_id):
    provider = Provider.query.get_or_404(provider_id)
    category = provider.category.name.lower()
    endpoints = ['login', 'add_user', 'recharge', 'redeem', 'reset_password', 'balance', 'agent_balance']
    response = None

    if request.method == 'POST':
        app.logger.info(f"Received POST data: {request.form}")
        try:
            action = request.form['action']
            payload = {}
            
            if action == 'login':
                payload = {
                    'provider_id': provider_id,
                    'username': request.form.get('username', ''),
                    'password': request.form.get('password', '')
                }
            elif action == 'add_user':
                payload = {
                    'provider_id': provider_id,
                    'new_username': request.form.get('new_username', ''),
                    'new_password': request.form.get('new_password', '')
                }
            elif action in ['recharge', 'redeem']:
                payload = {
                    'provider_id': provider_id,
                    'username': request.form.get('username', ''),
                    'amount': float(request.form.get('amount', 0))
                }
            elif action == 'reset_password':
                payload = {
                    'provider_id': provider_id,
                    'username': request.form.get('username', ''),
                    'new_password': request.form.get('new_password', '')
                }
            elif action == 'balance':
                payload = {
                    'provider_id': provider_id,
                    'username': request.form.get('username', '')
                }
            elif action == 'agent_balance':
                payload = {'provider_id': provider_id}

            app.logger.info(f"Action: {action}, Payload: {payload}")
            url = f"http://127.0.0.1:8080/{category}/{action}"
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
        except KeyError as e:
            app.logger.error(f"Missing form field: {e}")
            flash(f"Missing required field: {e}")
            result = {"message": "Error", "error": f"Missing field: {e}"}
        except ValueError as e:
            app.logger.error(f"Invalid value: {e}")
            flash("Invalid input value")
            result = {"message": "Error", "error": str(e)}
        except requests.RequestException as e:
            app.logger.error(f"API request failed: {e}")
            result = {"message": "Error", "error": str(e)}
        
        return render_template('admin/provider_management.html', provider=provider, endpoints=endpoints, response=result)

    return render_template('admin/provider_management.html', provider=provider, endpoints=endpoints, response=response)