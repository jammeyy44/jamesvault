"""
Authentication and request-safety helpers shared by the provider API and the site API.
"""
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import wraps

from flask import g, jsonify, request, session


def utcnow():
    """Naive UTC timestamp (all DateTime columns store UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def json_error(message, status=400, **extra):
    body = {"error": message}
    body.update(extra)
    return jsonify(body), status


def _bearer_token():
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def require_service_auth(func):
    """Guard for provider operations: logged-in admin or a valid, unexpired API token."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        player = current_player()
        if player is not None and player.status == "active" and player.role == "superadmin":
            return func(*args, **kwargs)
        from app import db
        from app.models import Token
        raw = _bearer_token()
        if raw:
            token = Token.query.filter_by(token=raw, is_deleted=False).first()
            if token and token.valid_until > utcnow():
                token.usage_count = (token.usage_count or 0) + 1
                db.session.commit()
                return func(*args, **kwargs)
        return {"error": "Authentication required"}, 401
    return wrapper


def is_public_ip(ip):
    if not ip or not isinstance(ip, str):
        return False
    try:
        import ipaddress
        addr = ipaddress.ip_address(ip.strip())
        return not (addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local)
    except ValueError:
        return False


def client_ip():
    """The customer's real public IP address.
    Checks headers from reverse proxies (CF-Connecting-IP, X-Real-IP, X-Forwarded-For)
    and validates that the IP is a genuine public address (as required by Paydora)."""
    from flask import current_app

    # 1. Direct proxy headers commonly set by Cloudflare, Nginx, or Vercel
    for header in ["CF-Connecting-IP", "True-Client-IP", "X-Real-IP"]:
        val = (request.headers.get(header) or "").strip()
        if is_public_ip(val):
            return val

    # 2. X-Forwarded-For: check entries for the public client IP
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        for p in parts:
            if is_public_ip(p):
                return p

    # 3. Direct remote address if it is public
    remote = (request.remote_addr or "").strip()
    if is_public_ip(remote):
        return remote

    # 4. Fallback for local development or loopback proxy connections
    # (Paydora rejects private/loopback 127.0.0.1 addresses with 400)
    fallback = current_app.config.get("SERVER_PUBLIC_IP", "162.0.238.169")
    return fallback


# --- rate limiting (per-process; put a shared limiter at the proxy for multi-worker deployments)
_hits = defaultdict(deque)


def rate_limited(key, limit, window_seconds):
    """Return True when `key` exceeded `limit` events in the last `window_seconds`."""
    from flask import current_app
    if not current_app.config.get("RATE_LIMITS_ENABLED", True):
        return False
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def rate_limit(name, limit, window_seconds):
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ident = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
            if rate_limited(f"{name}:{ident}", limit, window_seconds):
                return json_error("Too many requests. Please try again later.", 429)
            return func(*args, **kwargs)
        return wrapper
    return deco


# --- CSRF (synchronizer token kept in the session, sent back in a header)
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_ok():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    sent = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf", "")
    return bool(expected) and secrets.compare_digest(sent, expected)


# --- players
def current_player():
    from app import db
    from app.models_site import Player
    pid = session.get("player_id")
    if not pid:
        return None
    if getattr(g, "_player", None) is None or g._player.id != pid:
        g._player = db.session.get(Player, pid)
    return g._player


def player_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        player = current_player()
        if player is None:
            return json_error("Authentication required", 401)
        if player.status != "active":
            return json_error("This account is restricted. Please contact support.", 403)
        return func(*args, **kwargs)
    return wrapper


def admin_required(*roles):
    """Staff-only endpoint (signed-in player with an admin role). superadmin always passes; other roles
    must be listed. No roles = superadmin only."""
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            player = current_player()
            if player is None:
                return json_error("Authentication required", 401)
            if player.status != "active" or player.role == "player":
                return json_error("You do not have permission for this action", 403)
            if player.role != "superadmin" and player.role not in roles:
                return json_error("You do not have permission for this action", 403)
            return func(*args, **kwargs)
        return wrapper
    return deco


def audit(action, target=None, detail=None, actor_type=None, actor_id=None):
    """Append an audit record (committed with the caller's transaction)."""
    import json
    from app import db
    from app.models_site import AuditLog
    if actor_type is None:
        player = current_player()
        if player is not None:
            actor_type, actor_id = ("admin" if player.role != "player" else "player"), player.id
        else:
            actor_type = "anonymous"
    db.session.add(AuditLog(
        actor_type=actor_type, actor_id=actor_id, action=action, target=target,
        detail=json.dumps(detail, default=str)[:2000] if detail is not None else None,
        ip=(request.remote_addr if request else None),
    ))
