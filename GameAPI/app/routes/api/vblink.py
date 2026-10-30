from flask_restx import Namespace, Resource, fields
from app.utils.auth import require_service_auth

# Namespace kept for API compatibility; Vblink is served through Category 5.
vblink_ns = Namespace('vblink', description='VBLink game provider operations', decorators=[require_service_auth])

login_model = vblink_ns.model('LoginResponse', {
    'message': fields.String(description='Status message'),
})

@vblink_ns.route('/login')
class VBlinkLogin(Resource):
    @vblink_ns.doc('login')
    @vblink_ns.response(501, 'Not implemented', login_model)
    def post(self):
        """Not implemented. Use /category5/login for Vblink."""
        return {'message': 'Not implemented. Use /category5/login for Vblink.'}, 501
