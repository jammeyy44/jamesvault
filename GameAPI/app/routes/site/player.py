"""Player-facing endpoints: auth, account, favorites, wheel, referrals, notifications, support."""
import hashlib
import re
import secrets
from datetime import timedelta

from flask import current_app, jsonify, request, session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import (
    CatalogGame, Favorite, Notification, PasswordResetToken, Player, PromotionClaim, Referral,
    SupportTicket, TicketMessage, iso,
)
from app.utils.auth import (
    audit, csrf_token, current_player, json_error, player_required, rate_limit, rate_limited, utcnow,
)
from app.services import bonus
from app.utils.mailer import send_email

from . import site_bp
from .public import mask_username

USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,30}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _body():
    return request.get_json(silent=True) or {}


def _password_problem(password, username=""):
    if not isinstance(password, str) or len(password) < 10:
        return "Password must be at least 10 characters."
    if len(password) > 128:
        return "Password is too long."
    if username and password.lower() == username.lower():
        return "Password must not match your username."
    if password.isdigit() or password.isalpha():
        return "Use a mix of letters and numbers or symbols."
    return None


def _start_session(player):
    session.clear()
    session.permanent = True
    session['player_id'] = player.id
    csrf_token()  # fresh token for the new session (prevents fixation)


def _notify(player_id, title, body=None):
    db.session.add(Notification(player_id=player_id, title=title, body=body))


# ---------------------------------------------------------------- auth
@site_bp.route('/auth/register', methods=['POST'])
@rate_limit('register', 10, 3600)
def register():
    if not current_app.config["FEATURES"]["registration"]:
        return json_error("Registration is currently closed.", 403)
    data = _body()
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')
    if not USERNAME_RE.match(username):
        return json_error("Username must be 3-30 characters: letters, numbers or underscore.")
    if not EMAIL_RE.match(email) or len(email) > 254:
        return json_error("Enter a valid email address.")
    problem = _password_problem(password, username)
    if problem:
        return json_error(problem)
    if data.get('accept_terms') is not True:
        return json_error("You must accept the terms and confirm you meet the minimum age.")

    referrer = None
    ref_code = (data.get('referral_code') or '').strip().upper()
    if ref_code:
        referrer = Player.query.filter_by(referral_code=ref_code).first()

    player = Player(username=username, email=email, referred_by_id=referrer.id if referrer else None)
    player.set_password(password)
    db.session.add(player)
    try:
        db.session.flush()
        if referrer and referrer.id != player.id:
            db.session.add(Referral(referrer_id=referrer.id, referred_id=player.id))
            _notify(referrer.id, "New referral", "Someone signed up with your code. Rewards are confirmed after review.")
        if current_app.config["FEATURES"]["sandbox"]:  # sandbox only: lets developers see the Lucky Shop right away
            bonus.credit_diamonds(player.id, current_app.config["SANDBOX_WELCOME_DIAMONDS"], 'adjustment', 'sandbox_welcome', player.id)
        audit("player.register", target=username, actor_type="player", actor_id=player.id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("That username or email is already in use.", 409)
    _start_session(player)
    return jsonify({"player": player.to_dict(), "csrf_token": csrf_token()}), 201


@site_bp.route('/auth/login', methods=['POST'])
def login():
    data = _body()
    ident = (data.get('identifier') or '').strip().lower()
    password = data.get('password') or ''
    ip = request.remote_addr or '?'
    if rate_limited(f"login-ip:{ip}", 20, 900) or rate_limited(f"login-id:{ident}", 8, 900):
        return json_error("Too many attempts. Please wait and try again.", 429)
    player = Player.query.filter(func.lower(Player.username) == ident).first() or \
        Player.query.filter_by(email=ident).first()
    if not player or not player.check_password(password):
        audit("player.login_failed", target=ident[:60], actor_type="anonymous")
        db.session.commit()
        return json_error("Incorrect username/email or password.", 401)
    if player.status != 'active':
        return json_error("This account is restricted. Please contact support.", 403)
    player.last_login_at = utcnow()
    audit("player.login", actor_type="player", actor_id=player.id)
    db.session.commit()
    _start_session(player)
    return jsonify({"player": player.to_dict(), "csrf_token": csrf_token()})


@site_bp.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"ok": True, "csrf_token": csrf_token()})


@site_bp.route('/auth/me')
def me():
    player = current_player()
    if not player or player.status != 'active':
        return jsonify({"player": None})
    unread = Notification.query.filter_by(player_id=player.id, read_at=None).count()
    return jsonify({"player": player.to_dict(), "unread_notifications": unread})


@site_bp.route('/auth/forgot', methods=['POST'])
@rate_limit('forgot', 5, 3600)
def forgot_password():
    """Always answers the same way so the endpoint cannot be used to discover registered emails."""
    email = (_body().get('email') or '').strip().lower()
    player = Player.query.filter_by(email=email).first() if EMAIL_RE.match(email) else None
    if player and player.status == 'active':
        raw = secrets.token_urlsafe(32)
        PasswordResetToken.query.filter_by(player_id=player.id, used_at=None, purpose='reset').update({"used_at": utcnow()})
        db.session.add(PasswordResetToken(
            player_id=player.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=utcnow() + timedelta(minutes=current_app.config["PASSWORD_RESET_MINUTES"]),
        ))
        audit("player.password_reset_requested", actor_type="player", actor_id=player.id)
        db.session.commit()
        link = f"{current_app.config['FRONTEND_URL'].rstrip('/')}/reset-password?token={raw}"
        send_email(player.email, f"Reset your {current_app.config['BRAND']['name']} password",
                   f"Use this link within {current_app.config['PASSWORD_RESET_MINUTES']} minutes:\n{link}\n\n"
                   "If you did not request this, you can ignore this email.")
    return jsonify({"message": "If that email is registered, a reset link has been sent."})


@site_bp.route('/auth/reset', methods=['POST'])
@rate_limit('reset', 10, 3600)
def reset_password():
    data = _body()
    raw = data.get('token') or ''
    token = PasswordResetToken.query.filter_by(token_hash=hashlib.sha256(raw.encode()).hexdigest(), purpose='reset').first()
    if not token or token.used_at is not None or token.expires_at < utcnow():
        return json_error("This reset link is invalid or has expired.", 400)
    player = db.session.get(Player, token.player_id)
    problem = _password_problem(data.get('password'), player.username)
    if problem:
        return json_error(problem)
    player.set_password(data['password'])
    PasswordResetToken.query.filter_by(player_id=player.id, used_at=None, purpose='reset').update({"used_at": utcnow()})
    _notify(player.id, "Your password was changed", "If this wasn't you, contact support immediately.")
    audit("player.password_reset", actor_type="player", actor_id=player.id)
    db.session.commit()
    session.clear()
    return jsonify({"message": "Password updated. You can now sign in.", "csrf_token": csrf_token()})


@site_bp.route('/auth/verify-email/request', methods=['POST'])
@player_required
@rate_limit('verify-request', 5, 3600)
def request_email_verification():
    player = current_player()
    if player.email_verified:
        return jsonify({"message": "Your email is already confirmed."})
    raw = secrets.token_urlsafe(32)
    PasswordResetToken.query.filter_by(player_id=player.id, used_at=None, purpose='verify_email').update({"used_at": utcnow()})
    db.session.add(PasswordResetToken(
        player_id=player.id, purpose='verify_email', token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=utcnow() + timedelta(hours=24)))
    audit("player.verify_email_requested")
    db.session.commit()
    link = f"{current_app.config['FRONTEND_URL'].rstrip('/')}/verify-email?token={raw}"
    send_email(player.email, f"Confirm your {current_app.config['BRAND']['name']} email",
               f"Confirm your email address (link valid for 24 hours):\n{link}\n\nIf you didn't ask for this, ignore this email.")
    return jsonify({"message": "We've sent a confirmation link to your email."})


@site_bp.route('/auth/verify-email', methods=['POST'])
@rate_limit('verify-email', 20, 3600)
def verify_email():
    raw = str((request.get_json(silent=True) or {}).get('token') or '')
    token = PasswordResetToken.query.filter_by(token_hash=hashlib.sha256(raw.encode()).hexdigest(), purpose='verify_email').first()
    if not token or token.used_at is not None or token.expires_at < utcnow():
        return json_error("This confirmation link is invalid or has expired.", 400)
    player = db.session.get(Player, token.player_id)
    token.used_at = utcnow()
    player.email_verified = True
    _notify(player.id, "Email confirmed", "Thanks! You can now claim the Email task in the Bonus Zone.")
    audit("player.email_verified", actor_type="player", actor_id=player.id)
    db.session.commit()
    return jsonify({"message": "Your email is confirmed."})


# ---------------------------------------------------------------- account
@site_bp.route('/account/password', methods=['POST'])
@player_required
@rate_limit('chgpw', 10, 3600)
def change_password():
    data = _body()
    player = current_player()
    if not player.check_password(data.get('current_password') or ''):
        return json_error("Current password is incorrect.", 403)
    problem = _password_problem(data.get('new_password'), player.username)
    if problem:
        return json_error(problem)
    player.set_password(data['new_password'])
    _notify(player.id, "Your password was changed", "If this wasn't you, contact support immediately.")
    audit("player.password_change")
    db.session.commit()
    _start_session(player)  # rotate the session after a credential change
    return jsonify({"message": "Password updated.", "csrf_token": csrf_token()})


@site_bp.route('/account/profile', methods=['PATCH'])
@player_required
def update_profile():
    data = _body()
    player = current_player()
    email = (data.get('email') or '').strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        return json_error("Enter a valid email address.")
    if email != player.email:
        if not player.check_password(data.get('current_password') or ''):
            return json_error("Enter your current password to change your email.", 403)
        player.email = email
        player.email_verified = False
        _notify(player.id, "Email address changed")
        audit("player.email_change")
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("That email is already in use.", 409)
    return jsonify({"player": player.to_dict()})


@site_bp.route('/account/claims')
@player_required
def my_claims():
    player = current_player()
    rows = PromotionClaim.query.filter_by(player_id=player.id).order_by(PromotionClaim.id.desc()).limit(100).all()
    return jsonify({"items": [{"id": c.id, "promotion": c.promotion.title, "status": c.status,
                               "created_at": iso(c.created_at)} for c in rows]})


# ---------------------------------------------------------------- favorites
@site_bp.route('/favorites/<slug>', methods=['PUT', 'DELETE'])
@player_required
def toggle_favorite(slug):
    player = current_player()
    game = CatalogGame.query.filter_by(slug=slug).filter(CatalogGame.status != 'hidden').first()
    if not game:
        return json_error("Game not found", 404)
    existing = Favorite.query.filter_by(player_id=player.id, game_id=game.id).first()
    if request.method == 'PUT' and not existing:
        db.session.add(Favorite(player_id=player.id, game_id=game.id))
    elif request.method == 'DELETE' and existing:
        db.session.delete(existing)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # concurrent duplicate PUT: already a favorite
    return jsonify({"favorite": request.method == 'PUT'})


# ---------------------------------------------------------------- referrals
@site_bp.route('/referrals/me')
@player_required
def my_referrals():
    player = current_player()
    rows = Referral.query.filter_by(referrer_id=player.id).order_by(Referral.id.desc()).all()
    link = f"{current_app.config['FRONTEND_URL'].rstrip('/')}/register?ref={player.referral_code}"
    return jsonify({
        "code": player.referral_code, "link": link,
        "counts": {s: sum(1 for r in rows if r.status == s) for s in ("pending", "confirmed", "rejected")},
        "items": [{"player": mask_username(r.referred.username), "status": r.status, "reward": f"{r.reward_cents / 100:.2f}" if r.reward_cents else None,
                   "created_at": iso(r.created_at), "confirmed_at": iso(r.confirmed_at)} for r in rows],
        "bonus": f"{current_app.config['REFERRAL_BONUS_CENTS'] / 100:g}",
        "rules": f"When a friend who joined with your link makes their first deposit, ${current_app.config['REFERRAL_BONUS_CENTS'] / 100:g} "
                 "is added to your bonus balance. If that deposit is refunded the bonus is taken back. "
                 "Self-referrals and duplicate accounts are not eligible.",
    })


# ---------------------------------------------------------------- notifications
@site_bp.route('/notifications')
@player_required
def notifications():
    player = current_player()
    rows = Notification.query.filter_by(player_id=player.id).order_by(Notification.id.desc()).limit(50).all()
    return jsonify({"items": [{"id": n.id, "title": n.title, "body": n.body, "read": n.read_at is not None,
                               "created_at": iso(n.created_at)} for n in rows]})


@site_bp.route('/notifications/read', methods=['POST'])
@player_required
def mark_notifications_read():
    Notification.query.filter_by(player_id=current_player().id, read_at=None).update({"read_at": utcnow()})
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- support
def _ticket_dict(t, with_messages=False):
    d = {"id": t.id, "subject": t.subject, "status": t.status,
         "created_at": iso(t.created_at), "updated_at": iso(t.updated_at)}
    if with_messages:
        d["messages"] = [{"author": m.author_type, "body": m.body, "created_at": iso(m.created_at)} for m in t.messages]
    return d


@site_bp.route('/support/tickets', methods=['POST'])
@rate_limit('ticket', 10, 3600)
def create_ticket():
    data = _body()
    subject = (data.get('subject') or '').strip()
    body = (data.get('message') or '').strip()
    player = current_player()
    email = player.email if player else (data.get('email') or '').strip().lower()
    if not 3 <= len(subject) <= 160 or not 5 <= len(body) <= 5000:
        return json_error("Please provide a subject and a message.")
    if not player and not EMAIL_RE.match(email):
        return json_error("Enter a valid email address so we can reply.")
    ticket = SupportTicket(player_id=player.id if player else None, contact_email=email, subject=subject)
    ticket.messages.append(TicketMessage(author_type='player', body=body))
    db.session.add(ticket)
    audit("support.ticket_created", target=subject[:60])
    db.session.commit()
    return jsonify({"ticket": _ticket_dict(ticket)}), 201


@site_bp.route('/support/tickets')
@player_required
def my_tickets():
    rows = SupportTicket.query.filter_by(player_id=current_player().id).order_by(SupportTicket.updated_at.desc()).all()
    return jsonify({"items": [_ticket_dict(t) for t in rows]})


@site_bp.route('/support/tickets/<int:ticket_id>')
@player_required
def get_ticket(ticket_id):
    t = SupportTicket.query.filter_by(id=ticket_id, player_id=current_player().id).first()
    if not t:
        return json_error("Ticket not found", 404)
    return jsonify(_ticket_dict(t, with_messages=True))


@site_bp.route('/support/tickets/<int:ticket_id>/messages', methods=['POST'])
@player_required
@rate_limit('ticketmsg', 30, 3600)
def reply_ticket(ticket_id):
    t = SupportTicket.query.filter_by(id=ticket_id, player_id=current_player().id).first()
    if not t:
        return json_error("Ticket not found", 404)
    body = (_body().get('message') or '').strip()
    if not 1 <= len(body) <= 5000:
        return json_error("Write a message first.")
    t.messages.append(TicketMessage(author_type='player', body=body))
    t.status = 'open'
    db.session.commit()
    return jsonify(_ticket_dict(t, with_messages=True))
