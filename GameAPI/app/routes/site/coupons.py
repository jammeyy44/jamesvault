"""Coupons: admins generate codes, players redeem them for instant bonus cash (once per account)."""
import re
import secrets
from datetime import datetime

from flask import jsonify, request
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import Coupon, CouponRedemption, Player
from app.services import wallet as ledger
from app.utils.auth import admin_required, audit, current_player, json_error, player_required, rate_limit, utcnow

from . import site_bp

A = '/admin'
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
CODE_RE = re.compile(r'^[A-Z0-9-]{4,30}$')
MAX_AMOUNT_CENTS = 50000  # $500 per redemption


def _body():
    return request.get_json(silent=True) or {}


def _generate():
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


def _dt(v):
    return datetime.fromisoformat(v.replace('Z', '')).replace(tzinfo=None) if v else None


def _view(rows):
    ids = {c.assigned_player_id for c in rows if c.assigned_player_id}
    names = {p.id: p.username for p in Player.query.filter(Player.id.in_(ids or [0]))}
    return [c.to_dict(assigned=names.get(c.assigned_player_id)) for c in rows]


# ------------------------------------------------------------------ admin
@site_bp.route(f'{A}/coupons')
@admin_required()
def admin_coupons():
    rows = Coupon.query.order_by(Coupon.id.desc()).limit(300).all()
    return jsonify({"items": _view(rows)})


@site_bp.route(f'{A}/coupons', methods=['POST'])
@admin_required()
def admin_coupon_create():
    d = _body()
    try:
        cents = ledger.to_cents(d.get('amount'))
    except Exception:
        return json_error("Enter the bonus amount in dollars, e.g. 5 or 2.50.")
    if not 0 < cents <= MAX_AMOUNT_CENTS:
        return json_error("The amount must be between $0.01 and $500.00.")
    scope = d.get('scope')
    if scope not in ('single', 'many'):
        return json_error("Choose who can use this coupon: one person or many people.")
    assigned_id, cap = None, None
    if scope == 'single':
        who = (d.get('player') or '').strip().lower()
        player = Player.query.filter(db.or_(func.lower(Player.username) == who, func.lower(Player.email) == who)).first() if who else None
        if not player:
            return json_error("No account matches that username or email.")
        assigned_id, cap = player.id, 1
    elif d.get('max_redemptions') not in (None, ''):
        try:
            cap = int(d['max_redemptions'])
        except (TypeError, ValueError):
            return json_error("The maximum number of people must be a whole number.")
        if not 1 <= cap <= 1000000:
            return json_error("The maximum number of people must be at least 1.")
    try:
        expires = _dt(d.get('expires_at'))
    except ValueError:
        return json_error("That expiry date is not valid.")
    if expires and expires <= utcnow():
        return json_error("The expiry must be in the future.")
    code = (d.get('code') or '').strip().upper()
    if code and not CODE_RE.fullmatch(code):
        return json_error("Codes use letters, numbers and dashes only (4 to 30 characters).")
    for _ in range(5):
        candidate = code or _generate()
        if Coupon.query.filter_by(code=candidate).first():
            if code:
                return json_error("That code already exists.", 409)
            continue
        c = Coupon(code=candidate, note=(d.get('note') or '').strip()[:120] or None, reward_cents=cents, scope=scope,
                   assigned_player_id=assigned_id, max_redemptions=cap, expires_at=expires, created_by=current_player().id)
        db.session.add(c)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            if code:
                return json_error("That code already exists.", 409)
            continue
        audit("coupon.create", target=candidate, detail={"amount_cents": cents, "scope": scope, "assigned": assigned_id, "cap": cap})
        db.session.commit()
        return jsonify(_view([c])[0]), 201
    return json_error("Could not generate a unique code. Try again.", 500)


@site_bp.route(f'{A}/coupons/<int:cid>', methods=['PATCH'])
@admin_required()
def admin_coupon_update(cid):
    """Only switching a coupon on or off. Amount, scope and owner never change after creation."""
    c = db.session.get(Coupon, cid)
    if not c:
        return json_error("Not found", 404)
    d = _body()
    if 'is_active' not in d:
        return json_error("Nothing to change.")
    c.is_active = bool(d['is_active'])
    audit("coupon.activate" if c.is_active else "coupon.deactivate", target=c.code)
    db.session.commit()
    return jsonify(_view([c])[0])


# ------------------------------------------------------------------ player
@site_bp.route('/coupons/redeem', methods=['POST'])
@player_required
@rate_limit('coupon-redeem', 10, 3600)
def redeem_coupon():
    player = current_player()
    code = ((_body().get('code')) or '').strip().upper()
    if not CODE_RE.fullmatch(code):
        return json_error("That coupon code isn't valid.", 404, code="invalid_coupon")
    c = Coupon.query.filter_by(code=code).first()
    if not c or not c.is_active or (c.scope == 'single' and c.assigned_player_id != player.id):
        # same answer for "no such code" and "not yours", so codes cannot be probed
        return json_error("That coupon code isn't valid.", 404, code="invalid_coupon")
    if c.expires_at and c.expires_at <= utcnow():
        return json_error("This coupon has expired.", 410, code="coupon_expired")
    if CouponRedemption.query.filter_by(coupon_id=c.id, player_id=player.id).first():
        return json_error("You've already used this coupon.", 409, code="coupon_used")

    db.session.add(CouponRedemption(coupon_id=c.id, player_id=player.id, amount_cents=c.reward_cents))
    try:
        db.session.flush()  # unique (coupon, account): a second use, even a racing one, fails here
    except IntegrityError:
        db.session.rollback()
        return json_error("You've already used this coupon.", 409, code="coupon_used")
    stmt = update(Coupon).where(Coupon.id == c.id, Coupon.is_active.is_(True))
    if c.max_redemptions is not None:
        stmt = stmt.where(Coupon.redeemed_count < c.max_redemptions)  # compare-and-set: the cap cannot be overrun
    if db.session.execute(stmt.values(redeemed_count=Coupon.redeemed_count + 1)).rowcount != 1:
        db.session.rollback()
        return json_error("This coupon has been fully used.", 410, code="coupon_exhausted")
    ledger.credit(player.id, c.reward_cents, 'coupon', 'coupon', f"{c.id}:{player.id}", bucket="bonus")
    audit("coupon.redeem", target=c.code)
    db.session.commit()
    return jsonify({"amount": f"{c.reward_cents / 100:.2f}", "bonus_balance": ledger.fmt(ledger.balance_cents(player.id, "bonus"))})
