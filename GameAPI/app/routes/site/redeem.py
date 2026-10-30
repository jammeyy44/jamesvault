"""
Redeem winnings from a game account into the wallet, under the cashout table (app/services/cashout_rules.py).

Order of operations (money safety):
  1. read the authoritative game balance from the provider and check the rule;
  2. record a 'processing' RedeemRequest that LOCKS the deposit (unique constraint: one redeem per deposit; also stops two
     simultaneous requests) and commit, before anything moves;
  3. take the whole balance out of the game (provider call);
  4. only then credit the payout to the wallet; anything above the maximum is voided (never credited).
A refused provider call fails cleanly and releases the lock. An unclear outcome becomes 'needs_review': nothing is credited
until a person checks the provider and resolves it.
"""
import logging
import uuid
from decimal import Decimal

from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import CashRequest, Notification, RedeemRequest, iso
from app.services import cashout_rules as rules, wallet as ledger
from app.services.gateway import GatewayError, get_gateway
from app.utils.auth import audit, current_player, json_error, player_required, rate_limit, utcnow

from . import site_bp
from .accounts import _account, _game_or_404, _mode, _parse_amount, _provider_off

logger = logging.getLogger("jamesvault.redeem")


def _rule_view(rule):
    return {"row": rule["row"], "deposit": ledger.fmt(rule["deposit_cents"]), "min": ledger.fmt(rule["min_cents"]),
            "max": ledger.fmt(rule["max_cents"])}


def view(r):
    return {"id": r.id, "game": r.account.game.name, "status": r.status, "balance": ledger.fmt(r.balance_cents),
            "payout": ledger.fmt(r.payout_cents), "voided": ledger.fmt(r.void_cents), "deposit": ledger.fmt(r.deposit_cents),
            "min": ledger.fmt(r.min_cents), "max": ledger.fmt(r.max_cents), "sandbox": r.sandbox, "note": r.note,
            "created_at": iso(r.created_at)}


def _preview(player, game, acct):
    """Everything the player (and the redeem call) needs to know. Reads the live game balance."""
    out = {"game": game.name, "table": rules.TABLE, "note": rules.NOTE, "sandbox": _mode() == "sandbox",
           "latest_deposit": None, "rule": None, "game_balance": None, "payout": None, "voided": None,
           "can_redeem": False, "needs_confirm": False, "reason": None, "_dep": None, "_rule": None, "_balance": None}
    gateway = get_gateway()
    if gateway is None:
        out["reason"] = "Redeeming is not available yet."
        return out
    if _provider_off(game):
        out["reason"] = "This game is temporarily unavailable. Please try again later."
        return out
    dep = rules.latest_game_deposit(player.id, acct.id)
    rule = rules.limits(dep.amount_cents) if dep else None
    if dep is None or rule is None:
        out["reason"] = "Deposit cash ($5 or more) into this game to unlock redeeming. The amount you deposit into the game sets your limits."
        return out
    out.update(latest_deposit=ledger.fmt(dep.amount_cents), rule=_rule_view(rule), _dep=dep, _rule=rule)
    try:
        bal = ledger.to_cents(gateway.get_balance(acct))
    except GatewayError as e:
        out["reason"] = str(e)
        return out
    except Exception:
        logger.exception("could not read the game balance for redeem")
        out["reason"] = "We couldn't read your game balance right now. Please try again."
        return out
    out.update(game_balance=ledger.fmt(bal), _balance=bal)
    if RedeemRequest.query.filter_by(deposit_lock_id=dep.id).first():
        out["reason"] = "You've already redeemed for your latest deposit into this game. Add cash to this game to redeem again."
        return out
    if bal < rule["min_cents"]:
        out["reason"] = (f"You need at least ${ledger.fmt(rule['min_cents'])} in this game to redeem (set by your latest "
                         f"deposit into this game of ${ledger.fmt(dep.amount_cents)}). Your game balance is ${ledger.fmt(bal)}.")
        return out
    payout, voided = rules.outcome(bal, rule)
    out.update(payout=ledger.fmt(payout), voided=ledger.fmt(voided), can_redeem=True, needs_confirm=voided > 0)
    return out


def _public(p):
    return {k: v for k, v in p.items() if not k.startswith("_")}


@site_bp.route('/games/<slug>/redeem')
@player_required
@rate_limit('redeem-preview', 120, 3600)
def redeem_preview(slug):
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    return jsonify(_public(_preview(player, game, acct)))


@site_bp.route('/games/<slug>/redeem', methods=['POST'])
@player_required
@rate_limit('redeem', 20, 3600)
def redeem(slug):
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    data = request.get_json(silent=True) or {}
    key = str(data.get('idempotency_key') or '')[:64]
    if len(key) < 8:
        return json_error("Missing request id. Please try again.")
    prior = RedeemRequest.query.filter_by(player_id=player.id, idempotency_key=key).first()
    if prior:  # replay: return the original outcome, never redeem twice
        return jsonify(view(prior))

    pre = _preview(player, game, acct)
    if not pre["can_redeem"]:
        return json_error(pre["reason"] or "You can't redeem right now.", 409, code="not_redeemable")
    if pre["needs_confirm"] and data.get('confirm_void') is not True:
        return json_error(f"${pre['voided']} above your maximum will be voided. Confirm to continue.", 409,
                          code="confirm_void", payout=pre["payout"], voided=pre["voided"])

    dep, rule, bal = pre["_dep"], pre["_rule"], pre["_balance"]
    payout, voided = rules.outcome(bal, rule)
    rr = RedeemRequest(player_id=player.id, game_account_id=acct.id, deposit_lock_id=dep.id, deposit_cents=dep.amount_cents,
                       min_cents=rule["min_cents"], max_cents=rule["max_cents"], balance_cents=bal, payout_cents=payout,
                       void_cents=voided, status='processing', sandbox=_mode() == "sandbox", idempotency_key=key)
    db.session.add(rr)
    try:
        db.session.commit()  # locks the deposit BEFORE any money moves
    except IntegrityError:
        db.session.rollback()
        prior = RedeemRequest.query.filter_by(player_id=player.id, idempotency_key=key).first()
        if prior:
            return jsonify(view(prior))
        return json_error("You've already redeemed for your latest deposit (or another redeem is in progress).", 409, code="already_redeemed")

    try:
        get_gateway().redeem(acct, Decimal(bal) / 100)  # take the whole balance out of the game first
    except GatewayError as e:  # refused before anything changed: release the deposit so the player can retry
        rr.status, rr.deposit_lock_id, rr.note = 'failed', None, str(e)[:300]
        rr.processed_at = utcnow()
        db.session.commit()
        return jsonify(view(rr)), 201
    except Exception:  # outcome unknown: do NOT credit, a person checks the provider
        logger.exception("redeem outcome unknown for %s", rr.id)
        rr.status = 'needs_review'
        rr.note = "The game's answer was unclear. Our team is checking; nothing has been credited yet."
        rr.processed_at = utcnow()
        db.session.commit()
        return jsonify(view(rr)), 201

    ledger.credit(player.id, payout, 'redeem', 'redeem_request', rr.id)
    rr.status, rr.processed_at = 'completed', utcnow()
    rr.note = (f"${ledger.fmt(voided)} above the maximum was voided." if voided else None)
    db.session.add(Notification(player_id=player.id, title="Winnings redeemed",
                                body=f"${ledger.fmt(payout)} was added to your wallet from {game.name}."
                                     + (f" ${ledger.fmt(voided)} above your maximum was voided." if voided else "")))
    audit("redeem.completed", target=slug, detail={"balance": bal, "payout": payout, "voided": voided, "deposit": dep.amount_cents})
    db.session.commit()
    return jsonify(view(rr)), 201


@site_bp.route('/games/<slug>/sandbox/win', methods=['POST'])
@player_required
def sandbox_win(slug):
    """Development only (JV_SANDBOX): add test winnings to the sandbox game account so redeeming can be tried."""
    if not current_app.config["FEATURES"]["sandbox"]:
        return json_error("Not found", 404)
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    amount = _parse_amount((request.get_json(silent=True) or {}).get('amount'))
    if amount is None or not (0 < amount <= 10000):
        return json_error("Enter a test amount up to $10,000.")
    db.session.add(CashRequest(player_id=player.id, game_account_id=acct.id, amount=amount, source='win', sandbox=True,
                               status='completed', idempotency_key=f"win-{uuid.uuid4().hex}", note="Sandbox: test winnings",
                               processed_at=utcnow()))
    db.session.commit()
    return jsonify({"added": f"{amount:.2f}"}), 201
