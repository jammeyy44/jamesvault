from flask import Blueprint

api_bp = Blueprint('api', __name__)

from .category1 import category1_ns as category1_bp
from .category2 import category2_ns as category2_bp
from .category3 import category3_ns as category3_bp
from .category4 import category4_ns as category4_bp


api_bp.register_blueprint(category1_bp, url_prefix='/api/category1')
api_bp.register_blueprint(category2_bp, url_prefix='/api/category2')
api_bp.register_blueprint(category3_bp, url_prefix='/api/category3')
api_bp.register_blueprint(category4_bp, url_prefix='/api/category4')
