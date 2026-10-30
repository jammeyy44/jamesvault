"""Bonus Zone: tasks that earn diamonds, weekly streak and the Lucky Shop (boxes)."""
from datetime import timedelta

from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import BonusBox, BonusTask, PaymentOrder, PlayerReward, TaskClaim, WithdrawalOrder, iso
from app.services import bonus, wallet as ledger
from app.utils.auth import audit, current_player, json_error, player_required, rate_limit, utcnow

from . import site_bp

DAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _claimed_keys(player_id):
    return {k for (k,) in db.session.query(TaskClaim.claim_key).filter(TaskClaim.player_id == player_id)}


def _task_view(task, state):
    return {"key": task.key, "title": task.title, "description": task.description, "group": task.group,
            "kind": task.kind, "icon": task.icon, "reward": task.reward_diamonds, "state": state["state"],
            "reason": state["reason"], "progress": state["progress"], "available": state["available"]}


# "Test your luck": consecutive paid deposits without a cashout -> diamonds. (deposits needed, diamonds), highest tier first.
LUCK_TIERS = ((5, 15), (4, 8), (3, 5))
LUCK_MIN_DEPOSITS = LUCK_TIERS[-1][0]


def luck_reward(deposits: int) -> int:
    """Diamonds earned for this many consecutive deposits without a cashout (0 below the first tier)."""
    for need, diamonds in LUCK_TIERS:
        if deposits >= need:
            return diamonds
    return 0


def _evaluate_loss_streak(player_id: int):
    # Find latest cashout
    last_cashout = (
        WithdrawalOrder.query.filter_by(player_id=player_id)
        .filter(WithdrawalOrder.status.in_(['completed', 'pending_review', 'sending', 'submitted']))
        .order_by(WithdrawalOrder.created_at.desc())
        .first()
    )
    # Find latest loss streak claim
    last_claim = (
        TaskClaim.query.filter_by(player_id=player_id, task_key='loss_streak')
        .order_by(TaskClaim.created_at.desc())
        .first()
    )

    cutoff = None
    if last_cashout and last_claim:
        cutoff = max(last_cashout.created_at, last_claim.created_at)
    elif last_cashout:
        cutoff = last_cashout.created_at
    elif last_claim:
        cutoff = last_claim.created_at

    dep_query = PaymentOrder.query.filter_by(player_id=player_id, status='paid')
    if cutoff:
        dep_query = dep_query.filter(PaymentOrder.created_at > cutoff)
    losses = dep_query.count()

    # Void rule: if a cashout occurred after player had accumulated >= 3 deposits before claiming
    voided = False
    voided_amount = 0
    if last_cashout and (not last_claim or last_cashout.created_at > last_claim.created_at):
        prev_claim = (
            TaskClaim.query.filter_by(player_id=player_id, task_key='loss_streak')
            .filter(TaskClaim.created_at < last_cashout.created_at)
            .order_by(TaskClaim.created_at.desc())
            .first()
        )
        prev_cutoff = prev_claim.created_at if prev_claim else None
        prev_dep_query = PaymentOrder.query.filter_by(player_id=player_id, status='paid').filter(PaymentOrder.created_at < last_cashout.created_at)
        if prev_cutoff:
            prev_dep_query = prev_dep_query.filter(PaymentOrder.created_at > prev_cutoff)
        prev_count = prev_dep_query.count()
        if prev_count >= LUCK_MIN_DEPOSITS:
            voided = True
            voided_amount = luck_reward(prev_count)

    claimable = luck_reward(losses)

    return {
        "losses": losses,
        "claimable": claimable,
        "tiers": [{"deposits": need, "diamonds": diamonds} for need, diamonds in reversed(LUCK_TIERS)],
        "is_voided": voided and losses == 0,
        "voided_amount": voided_amount if (voided and losses == 0) else 0
    }


@site_bp.route('/bonus')
@player_required
def bonus_zone():
    player = current_player()
    today = utcnow().date()
    claimed, ctx = _claimed_keys(player.id), {}
    tasks = BonusTask.query.filter_by(is_active=True).order_by(BonusTask.group, BonusTask.sort_order).all()
    views = {t.key: _task_view(t, bonus.evaluate(player, t, today, claimed, ctx)) for t in tasks}

    week = [{"label": DAY_LABELS[i], "date": d.isoformat(), "today": d == today, "future": d > today,
             "claimed": f"daily_login:{player.id}:{d.isoformat()}" in claimed}
            for i, d in enumerate(bonus.week_days(today))]
    boxes = BonusBox.query.filter_by(is_active=True).order_by(BonusBox.sort_order, BonusBox.cost_diamonds).all()
    rewards = PlayerReward.query.filter_by(player_id=player.id).order_by(PlayerReward.id.desc()).limit(30).all()
    return jsonify({
        "diamonds": player.diamonds,
        "bonus_balance": ledger.fmt(player.bonus_cents),
        "boost": (lambda b: b.to_dict() if b else None)(bonus.active_boost(player.id)),
        "sandbox_notice": None,
        "tasks": [v for v in views.values() if v["group"] in ("general", "daily")],
        "streak": {"week": week, "task": views.get("weekly_streak")},
        "boxes": [dict(b.to_dict(), affordable=player.diamonds >= b.cost_diamonds) for b in boxes],
        "rewards": [r.to_dict() for r in rewards],
        "loss_streak": _evaluate_loss_streak(player.id),
    })


@site_bp.route('/bonus/tasks/<key>/claim', methods=['POST'])
@player_required
@rate_limit('bonus-claim', 60, 3600)
def claim_task(key):
    player = current_player()
    task = BonusTask.query.filter_by(key=key, is_active=True).first()
    if not task:
        return json_error("Task not found", 404)
    state = bonus.evaluate(player, task, utcnow().date(), _claimed_keys(player.id), {})
    if state["state"] == "claimed":
        return json_error("You've already claimed this one.", 409)
    if state["state"] != "claimable":
        return json_error(state["reason"] or "This task isn't complete yet.", 409)

    claim = TaskClaim(player_id=player.id, task_key=task.key, claim_key=state["claim_key"], diamonds=task.reward_diamonds)
    db.session.add(claim)
    try:
        db.session.flush()  # the unique claim_key makes a concurrent double-claim fail right here
        bonus.credit_diamonds(player.id, task.reward_diamonds, 'task', 'task_claim', claim.id)
        audit("bonus.task_claim", target=task.key, detail={"diamonds": task.reward_diamonds})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("You've already claimed this one.", 409)
    db.session.refresh(player)
    return jsonify({"claimed": task.key, "diamonds_awarded": task.reward_diamonds, "diamonds": player.diamonds}), 201


def _open_view(player, reward, replay=False):
    boost = bonus.active_boost(player.id)
    out = {"reward": reward.to_dict(), "diamonds": player.diamonds, "bonus_balance": ledger.fmt(player.bonus_cents),
           "boost": boost.to_dict() if boost else None, "note": reward.note}
    if replay:
        out["replay"] = True
    return out


@site_bp.route('/bonus/boxes/<int:box_id>/open', methods=['POST'])
@player_required
@rate_limit('bonus-open', 60, 3600)
def open_box(box_id):
    """Spend diamonds, receive the box's fixed reward. Idempotent on idempotency_key: a retry returns the same reward."""
    player = current_player()
    key = str((request.get_json(silent=True) or {}).get('idempotency_key') or '')[:64]
    if len(key) < 8:
        return json_error("Missing request id. Please try again.")
    prior = PlayerReward.query.filter_by(player_id=player.id, open_key=key).first()
    if prior:
        db.session.refresh(player)
        return jsonify(_open_view(player, prior, replay=True))
    box = db.session.get(BonusBox, box_id)
    if not box or not box.is_active:
        return json_error("That box isn't available.", 404)

    reward = PlayerReward(player_id=player.id, box_id=box.id, box_name=box.name, tone=box.tone, kind=box.prize_kind,
                          value_cents=box.prize_cents, value_percent=box.prize_percent, label=box.prize_label,
                          cost_diamonds=box.cost_diamonds, open_key=key)
    db.session.add(reward)
    try:
        db.session.flush()
        bonus.debit_diamonds(player.id, box.cost_diamonds, 'box', 'player_reward', reward.id)  # atomic: no overspend
        reward.note = bonus.apply_box_reward(player.id, reward, box)  # applied instantly, same transaction
        reward.status, reward.fulfilled_at = "applied", utcnow()
        audit("bonus.box_open", target=str(box.id), detail={"reward": reward.label, "cost": box.cost_diamonds})
        db.session.commit()
    except bonus.InsufficientDiamonds:
        db.session.rollback()
        db.session.refresh(player)
        need = box.cost_diamonds - player.diamonds
        return json_error(f"You need {need} more diamond{'s' if need != 1 else ''} to open this box.", 402,
                          code="insufficient_diamonds", diamonds=player.diamonds)
    except IntegrityError:
        db.session.rollback()
        prior = PlayerReward.query.filter_by(player_id=player.id, open_key=key).first()
        if prior:
            return jsonify(_open_view(current_player(), prior, replay=True))
        return json_error("Please try again.", 409)
    db.session.refresh(player)
    return jsonify(_open_view(player, reward)), 201


@site_bp.route('/bonus/loss-streak', methods=['GET'])
@player_required
def get_loss_streak():
    player = current_player()
    return jsonify(_evaluate_loss_streak(player.id))


@site_bp.route('/bonus/loss-streak/claim', methods=['POST'])
@player_required
@rate_limit('loss-streak-claim', 30, 3600)
def claim_loss_streak():
    player = current_player()
    st = _evaluate_loss_streak(player.id)
    if st["claimable"] < 1:
        return json_error(f"You need at least {LUCK_MIN_DEPOSITS} consecutive deposits without cashout to claim diamonds.", 400)
    diamonds = st["claimable"]
    claim_key = f"loss_streak:{player.id}:{utcnow().strftime('%Y%m%d%H%M%S%f')}"
    claim = TaskClaim(player_id=player.id, task_key="loss_streak", claim_key=claim_key, diamonds=diamonds)
    db.session.add(claim)
    try:
        db.session.flush()
        bonus.credit_diamonds(player.id, diamonds, 'task', 'loss_streak', claim.id)
        audit("bonus.loss_streak_claim", target="loss_streak", detail={"diamonds": diamonds, "deposits": st["losses"]})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("This streak reward has already been claimed.", 409)
    db.session.refresh(player)
    return jsonify({
        "claimed": "loss_streak",
        "diamonds_awarded": diamonds,
        "diamonds": player.diamonds,
        "losses": 0
    }), 201

