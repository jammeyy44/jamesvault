"""Game access (provider account), login details, balance and Add Cash requests."""
import logging
from decimal import Decimal, InvalidOperation

from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import CashRequest, CatalogGame, GameAccount, iso
from app.services import wallet as ledger
from app.services.gateway import AmbiguousOutcome, GatewayError, get_gateway, make_credentials
from app.utils.auth import audit, current_player, json_error, player_required, rate_limit, utcnow
from app.utils.crypto import decrypt_secret, encrypt_secret

from . import site_bp

logger = logging.getLogger("jamesvault.accounts")


def _game_or_404(slug):
    return CatalogGame.query.filter_by(slug=slug).filter(CatalogGame.status != 'hidden').first()


def _account(player, game):
    return GameAccount.query.filter_by(player_id=player.id, game_id=game.id, status='active').first()


def _mode():
    f = current_app.config["FEATURES"]
    if f["sandbox"]:
        return "sandbox"
    if f["game_accounts"]:
        return "live"
    return "disabled"


def _provider_off(game):
    return game.provider is not None and not game.provider.is_active


def _wallet_funded():
    """With the wallet on, Add Cash spends verified wallet funds and recharges automatically."""
    f = current_app.config["FEATURES"]
    return f["wallet"] and (f["sandbox"] or f["game_accounts"])


def _cash_enabled():
    f = current_app.config["FEATURES"]
    return _wallet_funded() or f["sandbox"] or (f["game_accounts"] and f["cash_requests"])


def _cash_cfg(game):
    cfg = current_app.config
    return {
        "min": str(cfg["CASH_MIN"]), "max": str(cfg["CASH_MAX"]), "quick": cfg["CASH_QUICK"],
        "cashout_min": str(game.cashout_min) if game.cashout_min is not None else None,
        "cashout_max": str(game.cashout_max) if game.cashout_max is not None else None,
    }


def _state(player, game):
    acct = _account(player, game)
    mode = _mode()
    return {
        "mode": mode,
        "game": {"slug": game.slug, "name": game.name, "category": game.category, "image_url": game.image_url,
                 "download_url": game.download_url,
                 "status": "maintenance" if _provider_off(game) else game.status},
        "account": {"username": acct.provider_username, "created_at": iso(acct.created_at)} if acct else None,
        "cash_enabled": _cash_enabled(),
        "cash": _cash_cfg(game),
        "sandbox_notice": None,
        "wallet_funded": _wallet_funded(),
        "bonus_enabled": mode != "disabled",
        "bonus_balance": ledger.fmt(player.bonus_cents),
        "bonus_min": "1",
        "wallet_balance": ledger.fmt(player.wallet_cents) if _wallet_funded() else None,
        "cash_notice": None if (mode == "sandbox" or _wallet_funded()) else (
            "Cash requests are confirmed by our team after payment, then credited to your game account."
            if _cash_enabled() else "Adding cash is not available yet."),
    }


@site_bp.route('/games/<slug>/access')
@player_required
def access_state(slug):
    game = _game_or_404(slug)
    if not game:
        return json_error("Game not found", 404)
    return jsonify(_state(current_player(), game))


@site_bp.route('/games/<slug>/access', methods=['POST'])
@player_required
@rate_limit('game-access', 20, 3600)
def get_access(slug):
    """Create (once) the player's account on this game. Safe to call repeatedly."""
    player = current_player()
    game = _game_or_404(slug)
    if not game:
        return json_error("Game not found", 404)
    if game.status == 'maintenance' or _provider_off(game):
        return json_error("This game is under maintenance. Please try again later.", 503, code="maintenance")
    gateway = get_gateway()
    if gateway is None:
        return json_error("Game accounts are not available yet.", 501, code="accounts_unavailable")

    existing = GameAccount.query.filter_by(player_id=player.id, game_id=game.id).first()
    if existing and existing.status == 'active':
        return jsonify(_state(player, game))
    if existing and existing.status != 'removed':  # a concurrent request is creating it right now
        return json_error("Your access is being created. Please try again in a moment.", 409)

    username, password = make_credentials(game.name)
    reusing = existing is not None  # the player removed an earlier login: give them a brand-new one on the same row
    if reusing:
        n = (GameAccount.query.filter_by(id=existing.id, status='removed')
             .update({"status": "pending", "provider_username": username, "password_enc": encrypt_secret(password),
                      "sandbox": _mode() == "sandbox", "created_at": utcnow()}, synchronize_session=False))
        db.session.commit()
        if n != 1:
            return json_error("Your access is being created. Please try again in a moment.", 409)
        acct = db.session.get(GameAccount, existing.id)
    else:
        acct = GameAccount(player_id=player.id, game_id=game.id, provider_username=username,
                           password_enc=encrypt_secret(password), status='pending', sandbox=_mode() == "sandbox")
        db.session.add(acct)
        try:
            db.session.commit()  # the unique (player, game) constraint makes double-clicks fail here, before any provider call
        except IntegrityError:
            db.session.rollback()
            return json_error("Your access is being created. Please try again in a moment.", 409)

    def undo():
        if reusing:
            acct.status = 'removed'
        else:
            db.session.delete(acct)
        db.session.commit()

    try:
        created = gateway.create_account(game, username, password)
    except GatewayError as e:
        undo()
        return json_error(str(e), 502, code="provider_error")
    except (AmbiguousOutcome, Exception):
        logger.exception("create_account failed")
        undo()
        return json_error("The game provider could not create your access. Please try again later.", 502, code="provider_error")
    try:
        if isinstance(created, dict):  # use the name and player id the provider actually created
            real_name = str(created.get("username") or "")[:60]
            if real_name and real_name != acct.provider_username:
                logger.info("provider renamed the login %s -> %s", acct.provider_username, real_name)
                acct.provider_username = real_name
            if created.get("user_id"):
                acct.provider_user_id = str(created["user_id"])[:40]
    except Exception:  # the provider created the login: never lose it because of a bookkeeping problem
        logger.exception("could not record the provider's account details")
    acct.status = 'active'
    audit("game_account.create", target=slug, detail={"sandbox": acct.sandbox})
    db.session.commit()
    return jsonify(_state(player, game)), 201


@site_bp.route('/games/<slug>/access/reset-password', methods=['POST'])
@player_required
@rate_limit('game-reset', 5, 3600)
def reset_game_password(slug):
    """New password for the player's game login (changed at the provider first, saved here only once that succeeded)."""
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    gateway = get_gateway()
    if gateway is None:
        return json_error("Game accounts are not available yet.", 501, code="accounts_unavailable")
    if _provider_off(game):
        return json_error("This game is temporarily unavailable. Please try again later.", 503, code="maintenance")
    _, new_password = make_credentials(game.name)
    try:
        gateway.reset_password(acct, new_password)
    except GatewayError as e:
        return json_error(str(e), 502, code="provider_error")
    except Exception:
        logger.exception("reset_password outcome unknown")
        return json_error("We couldn't confirm the change with the game. Your current password is unchanged here; if it stops working, contact support.", 502, code="provider_unclear")
    acct.password_enc = encrypt_secret(new_password)
    audit("game_account.password_reset", target=slug)
    db.session.commit()
    return jsonify({"ok": True})


@site_bp.route('/games/<slug>/access', methods=['DELETE'])
@player_required
@rate_limit('game-remove', 10, 3600)
def remove_access(slug):
    """Remove a game login from the player's list. Only when it holds nothing: the live game balance must be $0.00 and
    nothing may be pending. (The provider-side login is not deleted; a new login is created if they come back.)"""
    from app.models_site import RedeemRequest
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    gateway = get_gateway()
    if gateway is None:
        return json_error("Game accounts are not available yet.", 501, code="accounts_unavailable")
    pending_cash = CashRequest.query.filter(CashRequest.game_account_id == acct.id,
                                            CashRequest.status.in_(['awaiting_staff', 'processing', 'needs_review'])).count()
    pending_redeem = RedeemRequest.query.filter(RedeemRequest.game_account_id == acct.id,
                                                RedeemRequest.status.in_(['processing', 'needs_review'])).count()
    if pending_cash or pending_redeem:
        return json_error("You have a request in progress for this game. Try again once it is finished.", 409, code="pending")
    try:
        balance = gateway.get_balance(acct)
    except GatewayError as e:
        reason = (getattr(e, "reason", None) or "").lower()
        if "not found" in reason or reason.startswith("8:"):
            balance = Decimal("0")  # the provider has no such player, so there is nothing in it to protect
        else:
            return json_error("We couldn't check the game balance, so the login was not removed. Please try again in a minute. "
                              "If it keeps happening, contact support.", 502, code="provider_error")
    except Exception:
        logger.exception("remove_access: balance check failed")
        return json_error("We couldn't check the game balance, so the login was not removed. Please try again.", 502, code="provider_error")
    if Decimal(balance) >= Decimal("0.01"):
        return json_error(f"This login still has ${Decimal(balance):.2f}. Cash out or use it first, then remove it.", 409, code="has_balance")
    acct.status = 'removed'
    audit("game_account.removed", target=slug)
    db.session.commit()
    return jsonify({"ok": True})


@site_bp.route('/games/<slug>/access/credentials')
@player_required
@rate_limit('game-creds', 60, 3600)
def access_credentials(slug):
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    audit("game_account.credentials_viewed", target=slug)
    db.session.commit()
    return jsonify({"username": acct.provider_username, "password": decrypt_secret(acct.password_enc)})


@site_bp.route('/games/<slug>/balance')
@player_required
@rate_limit('game-balance', 120, 3600)
def access_balance(slug):
    """Always read live from the authoritative source; never cached."""
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    gateway = get_gateway()
    if gateway is None:
        return json_error("Balances are not available yet.", 501)
    try:
        bal = gateway.get_balance(acct)
    except GatewayError as e:
        return json_error(str(e), 502, code="provider_error")
    except (AmbiguousOutcome, Exception):
        logger.exception("get_balance failed")
        return json_error("We couldn't read your balance right now.", 502, code="provider_error")
    return jsonify({"balance": f"{Decimal(bal):.2f}", "currency": "USD", "as_of": iso(utcnow())})


def _parse_amount(raw):
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        return None
    return amount


@site_bp.route('/games/<slug>/cash', methods=['POST'])
@player_required
@rate_limit('game-cash', 20, 3600)
def add_cash(slug):
    player = current_player()
    game = _game_or_404(slug)
    acct = _account(player, game) if game else None
    if not acct:
        return json_error("You don't have access to this game yet.", 404)
    data = request.get_json(silent=True) or {}
    source = data.get('source') or 'wallet'
    if source not in ('wallet', 'bonus'):
        return json_error("Choose wallet or bonus.")
    if _provider_off(game):
        return json_error("This game is temporarily unavailable. Please try again later.", 503, code="maintenance")
    key = str(data.get('idempotency_key') or '')[:64]
    if len(key) < 8:
        return json_error("Missing request id. Please try again.")
    amount = _parse_amount(data.get('amount'))
    cfg = current_app.config

    if source == 'bonus':
        # Bonus balance works on any game we can reach (it needs no payment): at least $1, or the whole balance if less.
        if _mode() == "disabled":
            return json_error("Adding cash is not available yet.", 501, code="cash_unavailable")
        cents = ledger.to_cents(amount) if amount is not None else 0
        if cents <= 0 or amount > cfg["CASH_MAX"] or not (amount >= 1 or cents == player.bonus_cents):
            return json_error("Add at least $1 from your bonus balance (or your whole balance if it is under $1).")
    else:
        if not _cash_enabled():
            return json_error("Adding cash is not available yet.", 501, code="cash_unavailable")
        if amount is None or not (cfg["CASH_MIN"] <= amount <= cfg["CASH_MAX"]):
            return json_error(f"Enter an amount between ${cfg['CASH_MIN']} and ${cfg['CASH_MAX']}.")

    prior = CashRequest.query.filter_by(player_id=player.id, idempotency_key=key).first()
    if prior:  # replay of the same request: return the original outcome, never apply twice
        return jsonify(_cash_view(prior))

    if source == 'bonus' or _wallet_funded():
        return _add_cash_from_balance(player, game, acct, amount, key, source)

    sandbox = _mode() == "sandbox"
    req = CashRequest(player_id=player.id, game_account_id=acct.id, amount=amount, idempotency_key=key,
                      sandbox=sandbox, status='completed' if sandbox else 'awaiting_staff',
                      processed_at=utcnow() if sandbox else None,
                      note="Sandbox: test credit, no real money" if sandbox else None)
    db.session.add(req)
    try:
        audit("cash.request", target=slug, detail={"amount": str(amount), "sandbox": sandbox})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        prior = CashRequest.query.filter_by(player_id=player.id, idempotency_key=key).first()
        return jsonify(_cash_view(prior)) if prior else json_error("Please try again.", 409)
    return jsonify(_cash_view(req)), 201


def _add_cash_from_balance(player, game, acct, amount, key, bucket="wallet"):
    """Spend the wallet (verified payments) or the bonus balance and recharge the game account, exactly once.

    1. one transaction: record the request as 'processing' AND debit the bucket (atomic compare-and-set);
    2. call the provider; success -> completed; refused -> failed + refund; unknown outcome -> needs_review (funds stay held).
    """
    cents = ledger.to_cents(amount)
    req = CashRequest(player_id=player.id, game_account_id=acct.id, amount=amount, idempotency_key=key,
                      sandbox=_mode() == "sandbox", status='processing', source=bucket)
    db.session.add(req)
    try:
        db.session.flush()
        ledger.debit(player.id, cents, 'cash_to_game', 'cash_request', req.id, bucket=bucket)
        audit("cash.request", target=game.slug, detail={"amount": str(amount), "source": bucket})
        db.session.commit()
    except ledger.InsufficientFunds:
        db.session.rollback()
        bal = ledger.fmt(ledger.balance_cents(player.id, bucket))
        msg = (f"Your bonus balance (${bal}) is too low." if bucket == "bonus"
               else f"Your wallet balance (${bal}) is too low. Deposit first, then add cash.")
        return json_error(msg, 402, code="insufficient_funds", balance=bal, source=bucket)
    except IntegrityError:
        db.session.rollback()
        prior = CashRequest.query.filter_by(player_id=player.id, idempotency_key=key).first()
        return jsonify(_cash_view(prior)) if prior else json_error("Please try again.", 409)

    gateway = get_gateway()
    reason = None
    try:
        gateway.recharge(acct, amount)
        req.status, req.note = 'completed', ("Sandbox: test credit" if req.sandbox else None)
    except GatewayError as e:  # refused before anything was applied: give the money back
        req.status, req.note = 'failed', str(e)[:300]
        reason = getattr(e, "reason", None)  # the provider's own reason: shown to staff accounts only
        ledger.credit(player.id, cents, 'cash_refund', 'cash_request', req.id, bucket=bucket)
    except Exception:  # unknown outcome: keep the funds held for staff to reconcile
        logger.exception("recharge outcome unknown for cash request %s", req.id)
        req.status = 'needs_review'
        req.note = "Provider outcome unknown. Our team is checking; your funds are held."
    req.processed_at = utcnow()
    db.session.commit()
    view = _cash_view(req)
    if reason and player.role != "player":
        view["reason"] = str(reason)[:200]
    return jsonify(view), 201


def _cash_view(r):
    return {"id": r.id, "game": r.account.game.name, "amount": f"{r.amount:.2f}", "source": r.source, "status": r.status,
            "sandbox": r.sandbox, "note": r.note, "created_at": iso(r.created_at)}


@site_bp.route('/account/cash-requests')
@player_required
def my_cash_requests():
    rows = CashRequest.query.filter_by(player_id=current_player().id).order_by(CashRequest.id.desc()).limit(100).all()
    return jsonify({"items": [_cash_view(r) for r in rows]})
