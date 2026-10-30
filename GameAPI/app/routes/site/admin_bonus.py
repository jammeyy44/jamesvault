"""Admin: Bonus Zone tasks (reward/visibility), box rewards queue and manual diamond adjustments.
Boxes themselves are managed with the generic CRUD ('bonus-boxes' in admin.py)."""
from flask import jsonify, request

from app import db
from app.models_site import BonusTask, PlayerReward, Player, iso
from app.services import bonus
from app.utils.auth import admin_required, audit, current_player, json_error, utcnow

from . import site_bp

A = '/admin'


def _body():
    return request.get_json(silent=True) or {}


@site_bp.route(f'{A}/bonus-tasks')
@admin_required('content')
def admin_bonus_tasks():
    return jsonify({"items": [t.to_dict() for t in BonusTask.query.order_by(BonusTask.group, BonusTask.sort_order)]})


@site_bp.route(f'{A}/bonus-tasks/<int:tid>', methods=['PATCH'])
@admin_required('content')
def admin_bonus_task_update(tid):
    """Edit presentation and reward only. How a task is verified is fixed in code, never configurable here."""
    t = db.session.get(BonusTask, tid)
    if not t:
        return json_error("Not found", 404)
    d = _body()
    if (d.get('title') or '').strip():
        t.title = d['title'].strip()[:80]
    if 'description' in d:
        t.description = (d['description'] or '').strip()[:240] or None
    if 'reward_diamonds' in d:
        try:
            n = int(d['reward_diamonds'])
        except (TypeError, ValueError):
            return json_error("Reward must be a whole number.")
        if not 1 <= n <= 1000:
            return json_error("Reward must be between 1 and 1000 diamonds.")
        t.reward_diamonds = n
    if 'is_active' in d:
        t.is_active = bool(d['is_active'])
    if 'sort_order' in d:
        t.sort_order = int(d['sort_order'] or 0)
    audit("bonus.task_update", target=t.key, detail={k: v for k, v in d.items()})
    db.session.commit()
    return jsonify(t.to_dict())


@site_bp.route(f'{A}/bonus-rewards')
@admin_required('support', 'content')
def admin_bonus_rewards():
    q = PlayerReward.query
    if request.args.get('status'):
        q = q.filter_by(status=request.args['status'])
    rows = q.order_by(PlayerReward.id.desc()).limit(200).all()
    names = {p.id: p.username for p in Player.query.filter(Player.id.in_({r.player_id for r in rows} or [0]))}
    return jsonify({"items": [{"id": r.id, "player": names.get(r.player_id), "box": r.box_name, "reward": r.label,
                               "status": r.status, "note": r.note, "created_at": iso(r.created_at)} for r in rows]})


@site_bp.route(f'{A}/players/<int:pid>/diamonds', methods=['POST'])
@admin_required()
def admin_adjust_diamonds(pid):
    """Superadmin goodwill/correction. Positive credits, negative removes (never below zero). Audited."""
    d = _body()
    player = db.session.get(Player, pid)
    try:
        n = int(d.get('amount'))
    except (TypeError, ValueError):
        return json_error("Amount must be a whole number.")
    reason = (d.get('reason') or '').strip()
    if not player or n == 0 or abs(n) > 10000 or len(reason) < 3:
        return json_error("A non-zero amount (max 10000) and a reason are required.")
    ref = f"{current_player().id}:{pid}:{utcnow().timestamp()}"
    try:
        if n > 0:
            bonus.credit_diamonds(pid, n, 'adjustment', 'admin', ref)
        else:
            bonus.debit_diamonds(pid, -n, 'adjustment', 'admin', ref)
    except bonus.InsufficientDiamonds:
        db.session.rollback()
        return json_error("That would take the player below zero diamonds.", 409)
    audit("bonus.diamonds_adjust", target=str(pid), detail={"amount": n, "reason": reason[:100]})
    db.session.commit()
    db.session.refresh(player)
    return jsonify({"diamonds": player.diamonds})
