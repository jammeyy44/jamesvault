"""Free-spin wheel endpoints (deposit-gated, instant prizes)."""
from flask import current_app, jsonify
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import WheelSpin, iso
from app.services import bonus, wallet as ledger, wheel
from app.utils.auth import audit, current_player, json_error, player_required, rate_limit, utcnow

from . import site_bp


def _payload(player):
    prizes = wheel.active_prizes()
    total = sum(p.weight for p in prizes) or 1
    wallet_on = current_app.config["FEATURES"]["wallet"]
    st = wheel.state(player.id) if wallet_on else {"eligible": False, "can_spin": False, "closes_in": None, "next_spin_in": None}
    history = WheelSpin.query.filter_by(player_id=player.id).order_by(WheelSpin.id.desc()).limit(10).all()
    boost = bonus.active_boost(player.id)
    reason = None
    if not wallet_on:
        reason = "Free spins unlock with a deposit. Deposits are not available yet."
    elif not prizes:
        reason = "The wheel has no prizes configured right now."
    elif not st["eligible"] and st["next_spin_in"] is None:
        reason = "Make a deposit to unlock your free spin. It stays open for 24 hours."
    return {
        "enabled": wallet_on and bool(prizes), "reason": reason, **st,
        "can_spin": bool(st["can_spin"] and prizes),
        "prizes": [dict(p.to_dict(), odds_percent=round(100 * p.weight / total, 1)) for p in prizes],
        "history": [{"label": h.prize.label, "title": h.prize.title, "subtitle": h.prize.subtitle, "note": h.note,
                     "created_at": iso(h.created_at)} for h in history],
        "diamonds": player.diamonds, "bonus_balance": ledger.fmt(player.bonus_cents),
        "boost": boost.to_dict() if boost else None,
    }


@site_bp.route('/wheel')
@player_required
def wheel_state():
    return jsonify(_payload(current_player()))


@site_bp.route('/wheel/spin', methods=['POST'])
@player_required
@rate_limit('spin', 30, 3600)
def wheel_spin():
    player = current_player()
    if not current_app.config["FEATURES"]["wallet"]:
        return json_error("Free spins unlock with a deposit. Deposits are not available yet.", 409, code="wheel_unavailable")
    prizes = wheel.active_prizes()
    if not prizes:
        return json_error("The wheel has no prizes configured right now.", 409, code="wheel_unavailable")
    st = wheel.state(player.id)
    if not st["eligible"]:
        return json_error("Make a deposit to unlock your free spin.", 403, code="deposit_required")
    if not st["can_spin"]:
        return json_error("You've already used your free spin. The next one unlocks after another deposit once 24 hours have passed.",
                          409, code="cooldown")

    prize = wheel.pick(prizes)  # chosen here, server-side; the client only animates the result
    spin = WheelSpin(player_id=player.id, prize_id=prize.id, spin_key=f"{player.id}:dep{st['deposit_id']}", status="applied")
    db.session.add(spin)
    try:
        db.session.flush()  # unique spin_key: two simultaneous spins on the same deposit cannot both succeed
        spin.note = wheel.apply_prize(player.id, prize, spin)
        audit("wheel.spin", detail={"prize_id": prize.id, "kind": prize.kind, "value": prize.value})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("You've already used your free spin for this deposit.", 409, code="cooldown")
    db.session.refresh(player)
    return jsonify({"prize": prize.to_dict(), "note": spin.note, "state": _payload(player)}), 201
