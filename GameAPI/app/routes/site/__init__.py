"""
JSON API for the JamesVault site, mounted at /api/v1.

Players authenticate with a signed, HttpOnly session cookie. Every state-changing request must carry
the X-CSRF-Token header (obtain it from GET /api/v1/csrf). Admin endpoints live under /api/v1/admin.
"""
from flask import Blueprint, jsonify, request

from app.utils.auth import csrf_ok, csrf_token

site_bp = Blueprint('site', __name__, url_prefix='/api/v1')


@site_bp.before_request
def _csrf_guard():
    if not csrf_ok():
        return jsonify({"error": "Missing or invalid CSRF token"}), 403


@site_bp.after_request
def _no_store(resp):
    # Balances, claims and sessions must never be served from a shared cache.
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@site_bp.route('/csrf')
def get_csrf():
    return jsonify({"csrf_token": csrf_token()})


@site_bp.route('/health')
def health():
    """Liveness + database check for load balancers and uptime monitors."""
    from app import db
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "database_unavailable"}), 503


from . import public, player, accounts, admin, admin_providers, wallet, admin_wallet, bonus, admin_bonus, wheel, redeem, coupons  # noqa: E402,F401
