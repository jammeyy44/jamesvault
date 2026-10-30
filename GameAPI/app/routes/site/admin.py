"""
Admin JSON API (/api/v1/admin). Session login via Flask-Login, role checks on every route.
Roles: superadmin (everything), content (catalog/promotions/tournaments/wheel), support (players, tickets, claims).
Providers' stored credentials are never returned by any endpoint.
"""
import re
import secrets
from datetime import datetime

from flask import jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app import db
from app.models import Account, AccountType, Provider, Token
from app.models_site import (
    AuditLog, BonusBox, CashRequest, CatalogGame, Notification, Player, Promotion, PromotionClaim, Referral, SupportTicket,
    TicketMessage, Tournament, TournamentEntry, WheelPrize, WheelSpin, iso,
)
from app.utils.auth import admin_required, audit, current_player, hash_service_token, json_error, utcnow

from . import site_bp

A = '/admin'


def _body():
    return request.get_json(silent=True) or {}


@site_bp.route(f'{A}/overview')
@admin_required('support', 'content')
def overview():
    return jsonify({
        "players": Player.query.count(),
        "open_tickets": SupportTicket.query.filter(SupportTicket.status != 'closed').count(),
        "pending_claims": PromotionClaim.query.filter_by(status='pending').count(),
        "pending_referrals": Referral.query.filter_by(status='pending').count(),
        "pending_spins": WheelSpin.query.filter_by(status='pending').count(),
        "games": CatalogGame.query.count(),
        "live_promotions": sum(1 for p in Promotion.query.all() if p.window_state() == 'live'),
        "tournaments": Tournament.query.count(),
    })


# ---------------------------------------------------------------- generic CRUD for content
def _dt(v):
    if not v:
        return None
    return datetime.fromisoformat(v.replace('Z', '')).replace(tzinfo=None)


RESOURCES = {
    'games': (CatalogGame, {
        'slug': 'str', 'name': 'str', 'provider_id': 'int?', 'category': 'str', 'image_url': 'str?', 'download_url': 'str?',
        'description': 'str?', 'status': 'str', 'is_featured': 'bool', 'is_new': 'bool',
        'launch_supported': 'bool', 'sort_order': 'int', 'cashout_min': 'dec?', 'cashout_max': 'dec?',
    }, {'status': {'active', 'maintenance', 'hidden'}}),
    'promotions': (Promotion, {
        'slug': 'str', 'title': 'str', 'promo_type': 'str', 'description': 'str?', 'eligibility': 'str?',
        'reward_details': 'str?', 'terms': 'str?', 'image_url': 'str?', 'claim_rule': 'str',
        'new_player_days': 'int', 'coupon_code': 'str?', 'repeat': 'str', 'starts_at': 'dt?', 'ends_at': 'dt?',
        'is_active': 'bool',
    }, {'claim_rule': {'open', 'new_player', 'coupon', 'deposit'}, 'repeat': {'once', 'daily'}}),
    'tournaments': (Tournament, {
        'slug': 'str', 'title': 'str', 'description': 'str?', 'rules': 'str?', 'entry_conditions': 'str?',
        'prize_info': 'str?', 'image_url': 'str?', 'starts_at': 'dt', 'ends_at': 'dt', 'is_active': 'bool',
    }, {}),
    'bonus-boxes': (BonusBox, {
        'name': 'str', 'tone': 'str', 'description': 'str?', 'cost_diamonds': 'int', 'prize_kind': 'str',
        'prize_cents': 'int?', 'prize_percent': 'int?', 'boost_hours': 'int', 'is_active': 'bool', 'sort_order': 'int',
    }, {'tone': {'gift', 'crystal', 'gold', 'ember', 'emerald'},
        'prize_kind': {'freeplay', 'deposit_bonus_percent', 'bonus_cash'}}),
    'wheel-prizes': (WheelPrize, {
        'label': 'str?', 'kind': 'str', 'value': 'int', 'boost_hours': 'int', 'weight': 'int', 'is_active': 'bool',
    }, {'kind': {'diamonds', 'freeplay', 'boost_percent'}}),
}


def _coerce(kind, value):
    optional = kind.endswith('?')
    kind = kind.rstrip('?')
    if value in (None, ''):
        if optional:
            return None
        raise ValueError("required")
    if kind == 'str':
        return str(value).strip()
    if kind == 'int':
        return int(value)
    if kind == 'dec':
        from decimal import Decimal
        d = Decimal(str(value))
        if not d.is_finite() or d < 0:
            raise ValueError("invalid")
        return d.quantize(Decimal("0.01"))
    if kind == 'bool':
        return bool(value)
    if kind == 'dt':
        return _dt(value)
    raise ValueError(kind)


def _apply(obj, spec, enums, data, partial):
    for field, kind in spec.items():
        if field not in data:
            if partial or kind.endswith('?') or kind in ('bool',) or field in ('sort_order', 'new_player_days', 'weight', 'status', 'claim_rule', 'repeat', 'promo_type', 'category', 'boost_hours', 'kind', 'value'):
                continue
            raise ValueError(f"{field} is required")
        try:
            value = _coerce(kind, data[field])
        except (TypeError, ValueError):
            raise ValueError(f"Invalid value for {field}")
        if field in enums and value not in enums[field]:
            raise ValueError(f"Invalid value for {field}")
        if field in ('image_url', 'download_url') and value:
            ok = value.startswith(('https://', 'http://')) or (field == 'image_url' and value.startswith('/uploads/games/'))
            if not ok or len(value) > 500 or re.search(r'[\s"<>]', value):
                raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a web address starting with https://" + (" (or an uploaded image)" if field == 'image_url' else "") + ".")
        if field == 'slug' and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value or '') or (field == 'slug' and len(value) > 80):
            raise ValueError("Slug must be lowercase letters, numbers and single hyphens only (e.g. game-vault), up to 80 characters.")
        setattr(obj, field, value)


def _admin_dict(obj):
    if hasattr(obj, 'to_dict'):
        try:
            return obj.to_dict(public=False)
        except TypeError:
            return obj.to_dict()
    return obj.to_dict()


def _validate_wheel_prize(obj):
    """Keep wheel prizes sane: positive weight/value, sensible caps, and an auto label when left blank."""
    if not 1 <= (obj.weight or 0) <= 1000:
        raise ValueError("Weight must be between 1 and 1000.")
    caps = {'diamonds': 1000, 'freeplay': 10000, 'boost_percent': 100}
    if not 1 <= (obj.value or 0) <= caps.get(obj.kind, 0):
        raise ValueError({'diamonds': 'Diamonds must be 1-1000.', 'freeplay': 'Free play is in cents: 1-10000 ($100 max).',
                          'boost_percent': 'A boost must be 1-100 percent.'}.get(obj.kind, 'Invalid prize.'))
    if not 1 <= (obj.boost_hours or 0) <= 168:
        raise ValueError("Boost duration must be 1-168 hours.")
    obj.label = obj.label or f"{obj.title} {obj.subtitle}"


VALIDATORS = {'wheel-prizes': _validate_wheel_prize}


def _register_crud(name, model, spec, enums):
    roles = ('content',)

    def listing():
        return jsonify({"items": [_admin_dict(o) for o in model.query.order_by(model.id.desc()).all()]})

    def create():
        obj = model()
        try:
            _apply(obj, spec, enums, _body(), partial=False)
            if name in VALIDATORS:
                VALIDATORS[name](obj)
        except ValueError as e:
            db.session.rollback()  # discard the half-applied edit
            return json_error(str(e))
        db.session.add(obj)
        try:
            audit(f"{name}.create", target=str(getattr(obj, 'slug', '') or getattr(obj, 'label', '')))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return json_error("That slug is already in use.", 409)
        return jsonify(_admin_dict(obj)), 201

    def update(oid):
        obj = db.session.get(model, oid)
        if not obj:
            return json_error("Not found", 404)
        try:
            _apply(obj, spec, enums, _body(), partial=True)
            if name in VALIDATORS:
                VALIDATORS[name](obj)
        except ValueError as e:
            db.session.rollback()  # discard the half-applied edit
            return json_error(str(e))
        try:
            audit(f"{name}.update", target=str(oid))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return json_error("That slug is already in use.", 409)
        return jsonify(_admin_dict(obj))

    def delete(oid):
        obj = db.session.get(model, oid)
        if not obj:
            return json_error("Not found", 404)
        if name == 'games':
            from app.models_site import Favorite, GameAccount
            logins = GameAccount.query.filter_by(game_id=oid).count()
            if logins:  # their logins, balances and history belong to this game: keep it, but take it off the site
                return json_error(f"{logins} player login(s) exist for this game, so it can't be deleted without losing their history. "
                                  "Hide it instead: it disappears from the site and everything stays on record.", 409, code="has_logins")
            Favorite.query.filter_by(game_id=oid).delete()  # a favourite is just a bookmark: removed with the game
        db.session.delete(obj)
        try:
            audit(f"{name}.delete", target=str(oid))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return json_error("Cannot delete: it is referenced by other records. Disable it instead.", 409)
        return jsonify({"ok": True})

    base = f'{A}/{name}'
    site_bp.add_url_rule(base, f'admin_{name}_list', admin_required(*roles)(listing), methods=['GET'])
    site_bp.add_url_rule(base, f'admin_{name}_create', admin_required(*roles)(create), methods=['POST'])
    site_bp.add_url_rule(f'{base}/<int:oid>', f'admin_{name}_update', admin_required(*roles)(update), methods=['PATCH'])
    site_bp.add_url_rule(f'{base}/<int:oid>', f'admin_{name}_delete', admin_required(*roles)(delete), methods=['DELETE'])


for _name, (_model, _spec, _enums) in RESOURCES.items():
    _register_crud(_name, _model, _spec, _enums)


# ---------------------------------------------------------------- players
@site_bp.route(f'{A}/players')
@admin_required('support')
def admin_players():
    q = Player.query
    s = (request.args.get('search') or '').strip()
    if s:
        q = q.filter(Player.username.ilike(f"%{s}%") | Player.email.ilike(f"%{s}%"))
    return jsonify({"items": [p.to_dict() for p in q.order_by(Player.id.desc()).limit(200)]})


@site_bp.route(f'{A}/players/<int:pid>', methods=['PATCH'])
@admin_required('support')
def admin_player_update(pid):
    player = db.session.get(Player, pid)
    data = _body()
    if not player:
        return json_error("Not found", 404)
    me = current_player()
    if 'role' in data:
        # Granting or removing staff access is superadmin-only and cannot be used on yourself.
        if me.role != 'superadmin':
            return json_error("Only a superadmin can change roles.", 403)
        if data['role'] not in ('player', 'support', 'content', 'superadmin'):
            return json_error("Invalid role")
        if player.id == me.id:
            return json_error("You cannot change your own role.", 409)
        player.role = data['role']
        audit("player.role", target=str(pid), detail={"role": player.role})
    if 'status' in data:
        if data['status'] not in ('active', 'suspended'):
            return json_error("Invalid status")
        if player.id == me.id:
            return json_error("You cannot suspend yourself.", 409)
        player.status = data['status']
        audit("player.status", target=str(pid), detail={"status": player.status})
    db.session.commit()
    return jsonify(player.to_dict())


# ---------------------------------------------------------------- claims, spins, referrals
def _notify(pid, title, body=None):
    db.session.add(Notification(player_id=pid, title=title, body=body))


@site_bp.route(f'{A}/claims')
@admin_required('support', 'content')
def admin_claims():
    status = request.args.get('status')
    q = PromotionClaim.query
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(PromotionClaim.id.desc()).limit(200).all()
    names = {p.id: p.username for p in Player.query.filter(Player.id.in_({r.player_id for r in rows} or [0]))}
    return jsonify({"items": [{"id": c.id, "promotion": c.promotion.title, "player": names.get(c.player_id),
                               "status": c.status, "created_at": iso(c.created_at)} for c in rows]})


@site_bp.route(f'{A}/claims/<int:cid>', methods=['PATCH'])
@admin_required('support', 'content')
def admin_claim_update(cid):
    claim = db.session.get(PromotionClaim, cid)
    status = _body().get('status')
    if not claim or status not in ('fulfilled', 'rejected'):
        return json_error("Invalid request")
    if claim.status != 'pending':
        return json_error("This claim has already been processed.", 409)
    claim.status = status
    _notify(claim.player_id, f"Promotion {status}: {claim.promotion.title}")
    audit("claim.process", target=str(cid), detail={"status": status})
    db.session.commit()
    return jsonify({"ok": True})


@site_bp.route(f'{A}/spins')
@admin_required('support', 'content')
def admin_spins():
    rows = WheelSpin.query.order_by(WheelSpin.id.desc()).limit(200).all()
    names = {p.id: p.username for p in Player.query.filter(Player.id.in_({r.player_id for r in rows} or [0]))}
    return jsonify({"items": [{"id": s.id, "player": names.get(s.player_id), "prize": s.prize.label,
                               "status": s.status, "created_at": iso(s.created_at)} for s in rows]})


@site_bp.route(f'{A}/spins/<int:sid>', methods=['PATCH'])
@admin_required('support', 'content')
def admin_spin_update(sid):
    spin = db.session.get(WheelSpin, sid)
    if not spin or spin.status != 'pending':
        return json_error("Not found or already processed", 404)
    spin.status = 'fulfilled'
    _notify(spin.player_id, f"Reward fulfilled: {spin.prize.label}")
    audit("spin.fulfil", target=str(sid))
    db.session.commit()
    return jsonify({"ok": True})


@site_bp.route(f'{A}/referrals')
@admin_required('support')
def admin_referrals():
    rows = Referral.query.order_by(Referral.id.desc()).limit(200).all()
    ids = {r.referrer_id for r in rows}
    names = {p.id: p.username for p in Player.query.filter(Player.id.in_(ids or [0]))}
    return jsonify({"items": [{"id": r.id, "referrer": names.get(r.referrer_id), "referred": r.referred.username,
                               "status": r.status, "created_at": iso(r.created_at)} for r in rows]})


@site_bp.route(f'{A}/referrals/<int:rid>', methods=['PATCH'])
@admin_required('support')
def admin_referral_update(rid):
    ref = db.session.get(Referral, rid)
    status = _body().get('status')
    if not ref or status not in ('confirmed', 'rejected'):
        return json_error("Invalid request")
    if ref.status != 'pending':
        return json_error("This referral has already been processed.", 409)
    if ref.referrer_id == ref.referred_id:
        return json_error("Self-referrals are not eligible.", 409)
    ref.status = status
    ref.confirmed_at = utcnow() if status == 'confirmed' else None
    _notify(ref.referrer_id, f"Referral {status}")
    audit("referral.process", target=str(rid), detail={"status": status})
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- tournament scores (from verified results only)
@site_bp.route(f'{A}/tournaments/<int:tid>/entries')
@admin_required('content')
def admin_entries(tid):
    rows = TournamentEntry.query.filter_by(tournament_id=tid).order_by(TournamentEntry.score.desc()).all()
    return jsonify({"items": [{"id": e.id, "player": e.player.username, "score": str(e.score)} for e in rows]})


@site_bp.route(f'{A}/entries/<int:eid>', methods=['PATCH'])
@admin_required('content')
def admin_entry_score(eid):
    from decimal import Decimal, InvalidOperation
    entry = db.session.get(TournamentEntry, eid)
    try:
        score = Decimal(str(_body().get('score')))
    except InvalidOperation:
        return json_error("Invalid score")
    if not entry or not score.is_finite() or score < 0:
        return json_error("Invalid request")
    entry.score = score
    audit("tournament.score", target=str(eid), detail={"score": str(score)})
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- support tickets
@site_bp.route(f'{A}/tickets')
@admin_required('support')
def admin_tickets():
    rows = SupportTicket.query.order_by(SupportTicket.updated_at.desc()).limit(200).all()
    return jsonify({"items": [{"id": t.id, "subject": t.subject, "status": t.status, "email": t.contact_email,
                               "updated_at": iso(t.updated_at)} for t in rows]})


@site_bp.route(f'{A}/tickets/<int:tid>')
@admin_required('support')
def admin_ticket(tid):
    t = db.session.get(SupportTicket, tid)
    if not t:
        return json_error("Not found", 404)
    return jsonify({"id": t.id, "subject": t.subject, "status": t.status, "email": t.contact_email,
                    "messages": [{"author": m.author_type, "body": m.body, "created_at": iso(m.created_at)} for m in t.messages]})


@site_bp.route(f'{A}/tickets/<int:tid>/reply', methods=['POST'])
@admin_required('support')
def admin_ticket_reply(tid):
    t = db.session.get(SupportTicket, tid)
    data = _body()
    body = (data.get('message') or '').strip()
    if not t or not body:
        return json_error("Invalid request")
    t.messages.append(TicketMessage(author_type='staff', body=body))
    t.status = 'closed' if data.get('close') else 'answered'
    if t.player_id:
        _notify(t.player_id, "Support replied", t.subject)
    audit("ticket.reply", target=str(tid))
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- API tokens + audit log (superadmin)
@site_bp.route(f'{A}/tokens')
@admin_required()
def admin_tokens():
    rows = Token.query.filter_by(is_deleted=False).order_by(Token.id.desc()).all()
    return jsonify({"items": [{"id": t.id, "hint": "..." + t.token[-4:], "valid_until": iso(t.valid_until),
                               "usage_count": t.usage_count} for t in rows]})


@site_bp.route(f'{A}/tokens', methods=['POST'])
@admin_required()
def admin_token_create():
    from datetime import timedelta
    days = min(max(int(_body().get('days', 30)), 1), 365)
    account = Account(username=f"svc-{secrets.token_hex(4)}", email=f"svc-{secrets.token_hex(4)}@service.invalid",
                      password=generate_password_hash(secrets.token_urlsafe(24)), type=AccountType.STORE)
    db.session.add(account)
    db.session.flush()
    raw = secrets.token_urlsafe(32)
    db.session.add(Token(account_id=account.id, token=hash_service_token(raw), valid_until=utcnow() + timedelta(days=days)))
    audit("token.create", target=account.username)
    db.session.commit()
    return jsonify({"token": raw, "note": "Copy this now; it is not shown again."}), 201


@site_bp.route(f'{A}/tokens/<int:tid>', methods=['DELETE'])
@admin_required()
def admin_token_delete(tid):
    token = db.session.get(Token, tid)
    if not token:
        return json_error("Not found", 404)
    token.is_deleted = True
    audit("token.revoke", target=str(tid))
    db.session.commit()
    return jsonify({"ok": True})


@site_bp.route(f'{A}/audit')
@admin_required()
def admin_audit():
    rows = AuditLog.query.order_by(AuditLog.id.desc()).limit(300).all()
    return jsonify({"items": [{"id": a.id, "actor": f"{a.actor_type}:{a.actor_id}", "action": a.action,
                               "target": a.target, "ip": a.ip, "created_at": iso(a.created_at)} for a in rows]})


# ---------------------------------------------------------------- game thumbnail upload
def _sniff_image(head: bytes):
    """Identify the real image type from its first bytes (never trust the filename or Content-Type). SVG is refused."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


@site_bp.route(f'{A}/games/<int:gid>/thumbnail', methods=['POST'])
@admin_required('content')
def admin_game_thumbnail(gid):
    import os
    import uuid
    from flask import current_app
    from app.routes.uploads import games_dir
    game = db.session.get(CatalogGame, gid)
    if not game:
        return json_error("Not found", 404)
    f = request.files.get('file')
    if f is None:
        return json_error("Choose an image file.")
    data = f.read(2 * 1024 * 1024 + 1)
    if not data:
        return json_error("That file is empty.")
    if len(data) > 2 * 1024 * 1024:
        return json_error("The image is too large. Maximum size is 2 MB.", 413)
    kind = _sniff_image(data[:16])
    if kind is None:
        return json_error("Upload a PNG, JPEG or WebP image.")
    # Decode it for real (this also proves it is an image) and store a web-sized WebP: a 2 MB original would otherwise be
    # downloaded on every game card.
    import io
    from PIL import Image, UnidentifiedImageError
    Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        return json_error("We couldn't read that image. Try another PNG, JPEG or WebP.")
    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    if im.width > 720:
        im = im.resize((720, max(1, round(im.height * 720 / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80, method=6)
    optimized = buf.getvalue()
    name = f"{uuid.uuid4().hex}.webp"
    with open(os.path.join(games_dir(), name), "wb") as out:
        out.write(optimized)
    old = game.image_url or ""
    game.image_url = f"/uploads/games/{name}"
    audit("games.thumbnail", target=str(gid), detail={"bytes_in": len(data), "bytes_stored": len(optimized), "type": kind})
    db.session.commit()
    if old.startswith("/uploads/games/"):  # tidy up the file we are replacing (name pattern is ours, so no path tricks)
        prev = old.rsplit("/", 1)[1]
        from app.routes.uploads import NAME_RE
        if NAME_RE.match(prev):
            try:
                os.remove(os.path.join(games_dir(), prev))
            except OSError:
                pass
    return jsonify(game.to_dict())
