from flask_restx import Namespace, Resource
from app.services.factory import GameServiceFactory

api = Namespace('game', description='Game operations')

@api.route('/<string:provider>/recharge')
class Recharge(Resource):
    def post(self, provider):
        # Get request data
        data = api.payload
        service = GameServiceFactory.create_service(provider)
        result = service.recharge(data['username'], data['amount'])
        return result, 200 if result['success'] else 400

# TODO Add similar endpoints for other operations