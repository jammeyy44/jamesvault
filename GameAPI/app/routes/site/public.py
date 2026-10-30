"""Public (and optionally personalised) read endpoints: config, catalog, promotions, tournaments."""
from flask import current_app, jsonify, request
from sqlalchemy import func, or_

from app import db
from app.models_site import (
    CatalogGame, Favorite, Promotion, PromotionClaim, Tournament, TournamentEntry,
)
from app.models import Provider
from app.utils.auth import audit, current_player, json_error, player_required, utcnow

from . import site_bp

# Provider category -> launch adapter. Empty on purpose: no provider launch contract exists in this codebase.
LAUNCH_ADAPTERS = {}


def mask_username(name):
    if len(name) <= 2:
        return name[0] + "***"
    return name[:2] + "***" + name[-1]


@site_bp.route('/site/config')
def site_config():
    return jsonify({
        "brand": current_app.config["BRAND"],
        "features": current_app.config["FEATURES"],
        "launch_adapters": sorted(LAUNCH_ADAPTERS),
    })


# ---------------------------------------------------------------- catalog
@site_bp.route('/games')
def list_games():
    q = CatalogGame.query.filter(CatalogGame.status != 'hidden')
    search = (request.args.get('search') or '').strip()
    if search:
        like = f"%{search}%"
        q = q.filter(or_(CatalogGame.name.ilike(like), CatalogGame.description.ilike(like)))
    if request.args.get('provider'):
        q = q.filter(CatalogGame.provider_id == request.args.get('provider', type=int))
    if request.args.get('category'):
        q = q.filter(CatalogGame.category == request.args['category'])
    if request.args.get('featured') == '1':
        q = q.filter(CatalogGame.is_featured.is_(True))
    if request.args.get('new') == '1':
        q = q.filter(CatalogGame.is_new.is_(True))

    player = current_player()
    fav_ids = set()
    if player:
        fav_ids = {f.game_id for f in Favorite.query.filter_by(player_id=player.id)}
        if request.args.get('favorites') == '1':
            q = q.filter(CatalogGame.id.in_(fav_ids or [0]))

    page = max(request.args.get('page', 1, type=int), 1)
    per_page = min(max(request.args.get('per_page', 24, type=int), 1), 60)
    total = q.count()
    games = q.order_by(CatalogGame.sort_order, CatalogGame.name).offset((page - 1) * per_page).limit(per_page).all()

    providers = (db.session.query(Provider.id, Provider.name)
                 .join(CatalogGame, CatalogGame.provider_id == Provider.id)
                 .filter(CatalogGame.status != 'hidden').distinct().order_by(Provider.name).all())
    categories = [c for (c,) in db.session.query(CatalogGame.category)
                  .filter(CatalogGame.status != 'hidden').distinct().order_by(CatalogGame.category)]
    return jsonify({
        "items": [dict(g.to_dict(), favorite=g.id in fav_ids) for g in games],
        "total": total, "page": page, "per_page": per_page,
        "providers": [{"id": i, "name": n} for i, n in providers],
        "categories": categories,
    })


@site_bp.route('/games/<slug>')
def get_game(slug):
    game = CatalogGame.query.filter_by(slug=slug).filter(CatalogGame.status != 'hidden').first()
    if not game:
        return json_error("Game not found", 404)
    return jsonify(game.to_dict())


@site_bp.route('/games/<slug>/launch', methods=['POST'])
@player_required
def launch_game(slug):
    game = CatalogGame.query.filter_by(slug=slug).filter(CatalogGame.status != 'hidden').first()
    if not game:
        return json_error("Game not found", 404)
    if game.status == 'maintenance':
        return json_error("This game is under maintenance. Please try again later.", 503, code="maintenance")
    category = game.provider.category.name if game.provider else None
    adapter = LAUNCH_ADAPTERS.get(category)
    if not (current_app.config["FEATURES"]["game_launch"] and game.launch_supported and adapter):
        audit("game.launch_unsupported", target=slug)
        db.session.commit()
        return json_error("Launching this game is not available yet.", 501, code="launch_unsupported")
    # A provider adapter would create/retrieve the provider session here and return its launch URL.
    return json_error("Launch adapter did not return a session.", 502, code="launch_failed")


# ---------------------------------------------------------------- promotions
def _claim_key(promo, player_id, now):
    base = f"{promo.id}:{player_id}"
    return f"{base}:{now.date().isoformat()}" if promo.repeat == 'daily' else base


def promo_view(promo, player, now):
    d = promo.to_dict()
    d["claimed"] = False
    d["can_claim"] = False
    d["claim_blocked_reason"] = None
    if promo.window_state(now) != 'live':
        d["claim_blocked_reason"] = f"Promotion is {promo.window_state(now)}"
    elif promo.claim_rule not in ('open', 'new_player', 'coupon'):
        d["claim_blocked_reason"] = "Not claimable online"
    elif not player:
        d["claim_blocked_reason"] = "Sign in to claim"
    else:
        taken = PromotionClaim.query.filter_by(claim_key=_claim_key(promo, player.id, now)).first()
        if taken:
            d["claimed"] = True
            d["claim_blocked_reason"] = "Already claimed" if promo.repeat == 'once' else "Already claimed today"
        elif promo.claim_rule == 'new_player' and (now - player.created_at).days >= promo.new_player_days:
            d["claim_blocked_reason"] = "Only available to new players"
        else:
            d["can_claim"] = True
    d["requires_coupon"] = promo.claim_rule == 'coupon'
    return d


@site_bp.route('/promotions')
def list_promotions():
    now = utcnow()
    player = current_player()
    promos = (Promotion.query.filter(Promotion.is_active.is_(True))
              .order_by(Promotion.created_at.desc()).all())
    visible = [p for p in promos if p.window_state(now) in ('live', 'scheduled')]
    return jsonify({"items": [promo_view(p, player, now) for p in visible]})


@site_bp.route('/promotions/<slug>')
def get_promotion(slug):
    promo = Promotion.query.filter_by(slug=slug, is_active=True).first()
    if not promo:
        return json_error("Promotion not found", 404)
    return jsonify(promo_view(promo, current_player(), utcnow()))


@site_bp.route('/promotions/<slug>/claim', methods=['POST'])
@player_required
def claim_promotion(slug):
    from sqlalchemy.exc import IntegrityError
    now = utcnow()
    player = current_player()
    promo = Promotion.query.filter_by(slug=slug, is_active=True).first()
    if not promo:
        return json_error("Promotion not found", 404)
    if promo.window_state(now) != 'live':
        return json_error("This promotion is not currently available.", 409)
    if promo.claim_rule not in ('open', 'new_player', 'coupon'):
        return json_error("This promotion cannot be claimed online.", 409)
    if promo.claim_rule == 'new_player' and (now - player.created_at).days >= promo.new_player_days:
        return json_error("This promotion is only available to new players.", 403)
    if promo.claim_rule == 'coupon':
        code = ((request.get_json(silent=True) or {}).get('coupon') or '').strip()
        if not promo.coupon_code or code.lower() != promo.coupon_code.lower():
            return json_error("Invalid coupon code.", 403)

    claim = PromotionClaim(promotion_id=promo.id, player_id=player.id, claim_key=_claim_key(promo, player.id, now))
    db.session.add(claim)
    try:
        audit("promotion.claim", target=slug, detail={"claim_key": claim.claim_key})
        db.session.commit()  # the unique claim_key makes concurrent double-claims fail here
    except IntegrityError:
        db.session.rollback()
        return json_error("You have already claimed this promotion.", 409)
    return jsonify({"claim": {"id": claim.id, "status": claim.status}, "promotion": promo_view(promo, player, now)}), 201


# ---------------------------------------------------------------- tournaments
def _leaderboard(tournament, player, limit=50):
    rows = (TournamentEntry.query.filter_by(tournament_id=tournament.id)
            .order_by(TournamentEntry.score.desc(), TournamentEntry.created_at).all())
    board, me = [], None
    for rank, row in enumerate(rows, start=1):
        is_me = bool(player and row.player_id == player.id)
        if rank <= limit:
            board.append({"rank": rank, "player": mask_username(row.player.username), "score": str(row.score), "is_me": is_me})
        if is_me:
            me = {"rank": rank, "score": str(row.score)}
    return board, me, len(rows)


@site_bp.route('/tournaments')
def list_tournaments():
    items = Tournament.query.filter_by(is_active=True).order_by(Tournament.starts_at.desc()).all()
    phase = request.args.get('phase')
    out = [t.to_dict() for t in items if not phase or t.phase() == phase]
    return jsonify({"items": out})


@site_bp.route('/tournaments/<slug>')
def get_tournament(slug):
    t = Tournament.query.filter_by(slug=slug, is_active=True).first()
    if not t:
        return json_error("Tournament not found", 404)
    player = current_player()
    board, me, count = _leaderboard(t, player)
    return jsonify(dict(t.to_dict(), leaderboard=board, my_entry=me, entrants=count,
                        joined=me is not None,
                        scoring_note="Scores are entered by staff from verified results."))


@site_bp.route('/tournaments/<slug>/join', methods=['POST'])
@player_required
def join_tournament(slug):
    from sqlalchemy.exc import IntegrityError
    t = Tournament.query.filter_by(slug=slug, is_active=True).first()
    if not t:
        return json_error("Tournament not found", 404)
    if t.phase() == 'completed':
        return json_error("This tournament has ended.", 409)
    player = current_player()
    db.session.add(TournamentEntry(tournament_id=t.id, player_id=player.id))
    try:
        audit("tournament.join", target=slug)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("You have already joined this tournament.", 409)
    return jsonify({"joined": True}), 201
