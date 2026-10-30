"""
API routes for Category 2 game providers (e.g., Game Vault).
Handles operations with threading for async processing.
"""

from app.utils.auth import require_service_auth
from flask_restx import Namespace, Resource, fields
from app.services.category2_service import Category2Service
from threading import Thread
from app.models import Provider
from flask import current_app

category2_ns = Namespace('category2', description='Category 2 game provider operations', decorators=[require_service_auth])

# Request models
login_request = category2_ns.model('Category2Login', {
    'provider_id': fields.Integer(required=True, description='Provider ID'),
    'username': fields.String(required=True, description='Provider username'),
    'password': fields.String(required=True, description='Provider password')
})

user_request = category2_ns.model('Category2AddUser', {
    'provider_id': fields.Integer(required=True, description='Provider ID'),
    'new_username': fields.String(required=True, description='New account username'),
    'new_password': fields.String(required=True, description='New account password')
})

transaction_request = category2_ns.model('Category2Transaction', {
    'provider_id': fields.Integer(required=True, description='Provider ID'),
    'username': fields.String(required=True, description='Username'),
    'amount': fields.Float(required=True, description='Transaction amount')
})

reset_request = category2_ns.model('Category2ResetPassword', {
    'provider_id': fields.Integer(required=True, description='Provider ID'),
    'username': fields.String(required=True, description='Username'),
    'new_password': fields.String(required=True, description='New password')
})

balance_request = category2_ns.model('Category2Balance', {
    'provider_id': fields.Integer(required=True, description='Provider ID'),
    'username': fields.String(required=True, description='Username')
})

agent_balance_request = category2_ns.model('Category2AgentBalance', {
    'provider_id': fields.Integer(required=True, description='Provider ID')
})

response_model = category2_ns.model('Response', {
    'message': fields.String(description='Operation status message'),
    'error': fields.String(description='Error message if applicable', required=False),
    'token': fields.String(description='Authentication token', required=False),
    'username': fields.String(description='Username', required=False),
    'balance': fields.String(description='Balance', required=False)
})

@category2_ns.route('/login')
class Category2Login(Resource):
    @category2_ns.expect(login_request)
    @category2_ns.marshal_with(response_model, code=200)
    def post(self):
        """Authenticate with a Category 2 provider."""
        data = category2_ns.payload
        if data is None:
            return {"message": "Request body is missing or invalid", "error": "Please provide a valid JSON payload"}, 400
        provider = Provider.query.get(data['provider_id'])
        if not provider:
            current_app.logger.error(f"No provider found for ID: {data['provider_id']}")
            return {"message": "Invalid provider for Category 2"}, 400
        if provider.category.name != 'CATEGORY2':
            current_app.logger.error(f"Provider {provider.id} category mismatch: {provider.category}")
            return {"message": "Invalid provider for Category 2"}, 400
        service = Category2Service(provider)
        result = [None]
        def run_login():
            result[0] = service.login(data['username'], data['password'])
        thread = Thread(target=run_login)
        thread.start()
        thread.join()
        if result[0] is None:
            current_app.logger.error("Login operation timed out or failed")
            return {"message": "Login failed", "error": "Operation timed out or failed"}, 500
        status_code = 200 if "Login successful" in result[0]["message"] else 400
        return result[0], status_code

@category2_ns.route('/add_user')
class Category2AddUser(Resource):
    @category2_ns.expect(user_request)
    @category2_ns.marshal_with(response_model, code=201)
    def post(self):
        """Add a new user to a Category 2 provider."""
        data = category2_ns.payload
        if data is None:
            return {"message": "Request body is missing or invalid", "error": "Please provide a valid JSON payload"}, 400
        provider = Provider.query.get(data['provider_id'])
        if not provider:
            current_app.logger.error(f"No provider found for ID: {data['provider_id']}")
            return {"message": "Invalid provider for Category 2"}, 400
        if provider.category.name != 'CATEGORY2':
            current_app.logger.error(f"Provider {provider.id} category mismatch: {provider.category}")
            return {"message": "Invalid provider for Category 2"}, 400
        service = Category2Service(provider)
        result = [None]
        def run_add_user():
            result[0] = service.add_user(data['new_username'], data['new_password'])
        thread = Thread(target=run_add_user)
        thread.start()
        thread.join()
        if result[0] is None:
            current_app.logger.error("Add user operation timed out or failed")
            return {"message": "User creation failed", "error": "Operation timed out or failed"}, 500
        status_code = 201 if "User created" in result[0]["message"] else 400
        return result[0], status_code

@category2_ns.route('/recharge')
class Category2Recharge(Resource):
    @category2_ns.expect(transaction_request)
    @category2_ns.marshal_with(response_model, code=200)
    def post(self):
        """Recharge a user's account in a Category 2 provider."""
        data = category2_ns.payload
        if data is None:
            return {"message": "Request body is missing or invalid", "error": "Please provide a valid JSON payload"}, 400
        provider = Provider.query.get(data['provider_id'])
        if not provider:
            current_app.logger.error(f"No provider found for ID: {data['provider_id']}")
            return {"message": "Invalid provider for Category 2"}, 400
        if provider.category.name != 'CATEGORY2':
            current_app.logger.error(f"Provider {provider.id} category mismatch: {provider.category}")
            return {"message": "Invalid provider for Category 2"}, 400
        service = Category2Service(provider)
        result = [None]
        def run_recharge():
            result[0] = service.recharge(data['username'], data['amount'])
        thread = Thread(target=run_recharge)
        thread.start()
        thread.join()
        if result[0] is None:
            current_app.logger.error("Recharge operation timed out or failed")
            return {"message": "Recharge failed", "error": "Operation timed out or failed"}, 500
        status_code = 200 if "Recharged successfully" in result[0]["message"] else 400
        return result[0], status_code

@category2_ns.route('/redeem')
class Category2Redeem(Resource):
    @category2_ns.expect(transaction_request)
    @category2_ns.marshal_with(response_model, code=200)
    def post(self):
        """Redeem funds from a user's account in a Category 2 provider."""
        data = category2_ns.payload
        if data is None:
            return {"message": "Request body is missing or invalid", "error": "Please provide a valid JSON payload"}, 400
        provider = Provider.query.get(data['provider_id'])
        if not provider:
            current_app.logger.error(f"No provider found for ID: {data['provider_id']}")
            return {"message": "Invalid provider for Category 2"}, 400
        if provider.category.name != 'CATEGORY2':
            current_app.logger.error(f"Provider {provider.id} category mismatch: {provider.category}")
            return {"message": "Invalid provider for Category 2"}, 400
        service = Category2Service(provider)
        result = [None]
        def run_redeem():
            result[0] = service.redeem(data['username'], data['amount'])
        thread = Thread(target=run_redeem)
        thread.start()
        thread.join()
        if result[0] is None:
            current_app.logger.error("Redeem operation timed out or failed")
            return {"message": "Redeem failed", "error": "Operation timed out or failed"}, 500
        status_code = 200 if "Redeemed successfully" in result[0]["message"] else 400
        return result[0], status_code

@category2_ns.route('/reset_password')
class Category2ResetPassword(Resource):
    @category2_ns.expect(reset_request)
    @category2_ns.marshal_with(response_model, code=200)
    def post(self):
        """Reset a user's password in a Category 2 provider."""
        data = category2_ns.payload
        if data is None:
            return {"message": "Request body is missing or invalid", "error": "Please provide a valid JSON payload"}, 400
        provider = Provider.query.get(data['provider_id'])
        if not provider:
            current_app.logger.error(f"No provider found for ID: {data['provider_id']}")
            return {"message": "Invalid provider for Category 2"}, 400
        if provider.category.name != 'CATEGORY2':
            current_app.logger.error(f"Provider {provider.id} category mismatch: {provider.category}")
            return {"message": "Invalid provider for Category 2"}, 400
        service = Category2Service(provider)
        result = [None]
        def run_reset_password():
            result[0] = service.change_password(data['username'], data['new_password'])
        thread = Thread(target=run_reset_password)
        thread.start()
        thread.join()
        if result[0] is None:
            current_app.logger.error("Reset password operation timed out or failed")
            return {"message": "Password reset failed", "error": "Operation timed out or failed"}, 500
        status_code = 200 if "Password changed successfully" in result[0]["message"] else 400
        return result[0], status_code

@category2_ns.route('/balance')
class Category2Balance(Resource):
    @category2_ns.expect(balance_request)
    @category2_ns.marshal_with(response_model, code=200)
    def post(self):
        """Fetch a user's balance from a Category 2 provider."""
        data = category2_ns.payload
        if data is None:
            return {"message": "Request body is missing or invalid", "error": "Please provide a valid JSON payload"}, 400
        provider = Provider.query.get(data['provider_id'])
        if not provider:
            current_app.logger.error(f"No provider found for ID: {data['provider_id']}")
            return {"message": "Invalid provider for Category 2"}, 400
        if provider.category.name != 'CATEGORY2':
            current_app.logger.error(f"Provider {provider.id} category mismatch: {provider.category}")
            return {"message": "Invalid provider for Category 2"}, 400
        service = Category2Service(provider)
        result = [None]
        def run_get_balances():
            result[0] = service.get_balances(data['username'])
        thread = Thread(target=run_get_balances)
        thread.start()
        thread.join()
        if result[0] is None:
            current_app.logger.error("Balance fetch operation timed out or failed")
            return {"message": "Balance fetch failed", "error": "Operation timed out or failed"}, 500
        status_code = 200 if "Balance fetched" in result[0]["message"] else 400
        return result[0], status_code

@category2_ns.route('/agent_balance')
class Category2AgentBalance(Resource):
    @category2_ns.expect(agent_balance_request)
    @category2_ns.marshal_with(response_model, code=200)
    def post(self):
        """Fetch the agent's balance from a Category 2 provider."""
        data = category2_ns.payload
        if data is None:
            return {"message": "Request body is missing or invalid", "error": "Please provide a valid JSON payload"}, 400
        provider = Provider.query.get(data['provider_id'])
        if not provider:
            current_app.logger.error(f"No provider found for ID: {data['provider_id']}")
            return {"message": "Invalid provider for Category 2"}, 400
        if provider.category.name != 'CATEGORY2':
            current_app.logger.error(f"Provider {provider.id} category mismatch: {provider.category}")
            return {"message": "Invalid provider for Category 2"}, 400
        service = Category2Service(provider)
        result = [None]
        def run_get_agent_balance():
            result[0] = service.get_agent_balance()
        thread = Thread(target=run_get_agent_balance)
        thread.start()
        thread.join()
        if result[0] is None:
            current_app.logger.error("Agent balance fetch operation timed out or failed")
            return {"message": "Agent balance fetch failed", "error": "Operation timed out or failed"}, 500
        status_code = 200 if "Agent balance fetched" in result[0]["message"] else 400
        return result[0], status_code