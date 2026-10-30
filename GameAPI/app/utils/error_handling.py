"""
Utility for handling errors in API routes.
"""

from functools import wraps
from flask import jsonify

def handle_errors(f):
    """Decorator to handle errors in API routes."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return wrapped