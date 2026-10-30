"""Player wallet: balance, payment methods, deposits (pay-in), cashouts (pay-out) and history."""
import re
import time
from decimal import Decimal, InvalidOperation

from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import PaymentMethodSetting, PaymentOrder, WalletEntry, WithdrawalOrder, iso
from app.services import bonus, cashout_rules
from app.services import wallet as ledger
from app.services.payments import ACCEPTED_AMOUNTS, PAYOUT_FIELDS, PaymentError, get_payments, normalize_value, payments_mode
from app.utils.auth import audit, client_ip, current_player, json_error, player_required, rate_limit, utcnow

from . import site_bp

FINGERPRINT_RE = re.compile(r'^[A-Za-z0-9_-]{8,128}$')
_methods_cache = {"at": 0.0, "mode": None, "data": None}


def _parse_amount(raw):
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
        return None
    return amount


def _provider_methods(payments):
    """Method lists come from the provider (they change as methods are enabled). Cached for 60s; balances never are."""
    now = time.monotonic()
    mode = payments_mode()
    if _methods_cache["data"] is not None and _methods_cache["mode"] == mode and now - _methods_cache["at"] < 60:
        return _methods_cache["data"]
    data = payments.methods()
    _methods_cache.update(at=now, mode=mode, data=data)
    return data


def _decorate(methods):
    """Join provider methods with admin presentation settings (label/badge/order/enabled)."""
    settings = {s.value: s for s in PaymentMethodSetting.query.all()}
    out = []
    for m in methods:
        value = normalize_value(m.get("value"))
        s = settings.get(value)
        if s is not None and not s.is_enabled:
            continue
        out.append({"id": m["id"], "value": value, "name": (s.label if s and s.label else m.get("name") or value),
                    "badge": s.badge if s else None, "badge_tone": s.badge_tone if s else None,
                    "amounts": ACCEPTED_AMOUNTS.get(value), "order": s.sort_order if s else 0})
    return sorted(out, key=lambda x: (x["order"], x["name"]))


@site_bp.route('/wallet')
@player_required
def wallet():
    player = current_player()
    mode = payments_mode()
    cfg = current_app.config
    base = {"mode": mode, "currency": "USD", "enabled": mode != "disabled",
            "cashout": {"min": str(cfg["CASHOUT_MIN"]), "max": str(cfg["CASHOUT_MAX"])},
            "deposit": {"min": str(cfg["DEPOSIT_MIN"]), "max": str(cfg["DEPOSIT_MAX"])},
            "payout_fields": PAYOUT_FIELDS, "deposit_methods": [], "withdrawal_methods": [], "notice": None,
            "sandbox_notice": None}
    if mode == "disabled":
        base.update(balance=None, transactions=[], reason="Deposits and withdrawals are not available yet.")
        return jsonify(base)
    base["balance"] = ledger.fmt(player.wallet_cents)  # always read fresh from the database
    base["bonus_balance"] = ledger.fmt(player.bonus_cents)
    dep = cashout_rules.latest_deposit(player.id)
    rule = cashout_rules.limits(dep.amount_cents) if dep else None
    base["cashout_rule"] = {"table": cashout_rules.TABLE, "note": cashout_rules.NOTE,
                            "latest_deposit": ledger.fmt(dep.amount_cents) if dep else None,
                            "row": rule["row"] if rule else None,
                            "min": ledger.fmt(rule["min_cents"]) if rule else None, "max": ledger.fmt(rule["max_cents"]) if rule else None}
    boost = bonus.active_boost(player.id)
    base["boost"] = boost.to_dict() if boost else None
    try:
        methods = _provider_methods(get_payments())
        base["deposit_methods"] = _decorate(methods["deposits"])
        base["withdrawal_methods"] = [m for m in _decorate(methods["withdrawals"]) if m["value"] in PAYOUT_FIELDS]
    except PaymentError as e:
        base["notice"] = str(e)
    return jsonify(base)


def _deposit_view(o):
    return {"id": o.id, "type": "deposit", "method": o.method_name, "amount": ledger.fmt(o.amount_cents),
            "status": o.status, "sandbox": o.sandbox, "payment_url": o.payment_url if o.status == 'pending' else None,
            "bonus": ledger.fmt(o.bonus_cents) if o.bonus_cents else None, "bonus_percent": o.bonus_percent,
            "reference": o.reference_id, "created_at": iso(o.created_at)}


def _withdrawal_view(w):
    return {"id": w.id, "type": "cashout", "method": w.method_name, "amount": ledger.fmt(w.amount_cents),
            "status": w.status, "sandbox": w.sandbox, "reference": w.reference_id, "created_at": iso(w.created_at)}


@site_bp.route('/wallet/deposits', methods=['POST'])
@player_required
@rate_limit('wallet-deposit', 20, 3600)
def create_deposit():
    player = current_player()
    payments = get_payments()
    if payments is None:
        return json_error("Deposits are not available yet.", 501, code="wallet_unavailable")
    d = request.get_json(silent=True) or {}
    key = str(d.get('idempotency_key') or '')[:64]
    fingerprint = str(d.get('device_fingerprint') or '')
    if len(key) < 8:
        return json_error("Missing request id. Please try again.")
    if not FINGERPRINT_RE.match(fingerprint):
        return json_error("We couldn't verify your device. Please refresh and try again.")
    prior = PaymentOrder.query.filter_by(player_id=player.id, idempotency_key=key).first()
    if prior:  # replay: return the original order, never create a second one
        return jsonify(_deposit_view(prior))

    try:
        methods = _provider_methods(payments)
    except PaymentError as e:
        return json_error(str(e), 502, code="payment_unavailable")
    method = next((m for m in _decorate(methods["deposits"]) if m["id"] == d.get('method_id')), None)
    if method is None:
        return json_error("That payment method is not available.")
    amount = _parse_amount(d.get('amount'))
    if amount is None:
        return json_error("Enter a valid amount.")
    accepted = ACCEPTED_AMOUNTS.get(method["value"])
    if accepted and float(amount) not in [float(a) for a in accepted]:
        return json_error(f"{method['name']} accepts: " + ", ".join(f"${a:g}" for a in accepted))
    cfg = current_app.config
    if not accepted and not (cfg["DEPOSIT_MIN"] <= amount <= cfg["DEPOSIT_MAX"]):
        return json_error(f"Enter an amount between ${cfg['DEPOSIT_MIN']:g} and ${cfg['DEPOSIT_MAX']:g}.")
    ip = client_ip()
    if not ip:
        return json_error("We couldn't verify your connection. Please try again.")

    boost = bonus.active_boost(player.id)  # snapshot: the boost running NOW decides the bonus, even if payment lands later
    order = PaymentOrder(player_id=player.id, method_id=method["id"], method_value=method["value"],
                         method_name=method["name"], amount_cents=ledger.to_cents(amount), idempotency_key=key,
                         sandbox=payments.name == "sandbox", bonus_percent=boost.percent if boost else None)
    db.session.add(order)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        prior = PaymentOrder.query.filter_by(player_id=player.id, idempotency_key=key).first()
        return jsonify(_deposit_view(prior)) if prior else json_error("Please try again.", 409)

    frontend = current_app.config["FRONTEND_URL"].rstrip("/")
    return_url = f"{frontend}/dashboard?tab=wallet" if frontend.startswith("https://") and len(frontend) < 100 else None
    try:
        resp = payments.create_deposit(method_id=method["id"], amount=amount, customer_ip=ip,
                                       device_fingerprint=fingerprint, user_name=player.username,
                                       return_url=return_url, user_agent=request.headers.get("User-Agent", ""),
                                       idempotency_key=f"jv-dep-{order.id}")
    except PaymentError as e:
        order.status, order.note = 'failed', str(e)[:200]
        db.session.commit()
        return json_error(str(e), 400 if e.definitive else 502, code="payment_failed")

    order.provider_deposit_id = resp.get("id")
    order.reference_id = resp.get("referenceId")
    order.payment_url = resp.get("paymentUrl")
    if resp.get("isChimney"):
        # Direct-pay Chime: the provider creates nothing until money lands. Staff match the payment (see admin).
        order.note = "Direct Chime payment: confirmed when the payment arrives."
    if order.sandbox:
        ledger.credit(player.id, order.amount_cents, 'deposit', 'payment_order', order.id)
        order.status, order.paid_at = 'paid', utcnow()
        bonus.grant_deposit_bonus(order)
    audit("wallet.deposit_created", target=str(order.id), detail={"amount_cents": order.amount_cents, "method": method["value"]})
    db.session.commit()
    return jsonify(_deposit_view(order)), 201


@site_bp.route('/wallet/withdrawals', methods=['POST'])
@player_required
@rate_limit('wallet-withdraw', 10, 3600)
def create_withdrawal():
    player = current_player()
    payments = get_payments()
    if payments is None:
        return json_error("Cashouts are not available yet.", 501, code="wallet_unavailable")
    d = request.get_json(silent=True) or {}
    key = str(d.get('idempotency_key') or '')[:64]
    if len(key) < 8:
        return json_error("Missing request id. Please try again.")
    prior = WithdrawalOrder.query.filter_by(player_id=player.id, idempotency_key=key).first()
    if prior:
        return jsonify(_withdrawal_view(prior))
    try:
        methods = _provider_methods(payments)
    except PaymentError as e:
        return json_error(str(e), 502, code="payment_unavailable")
    method = next((m for m in _decorate(methods["withdrawals"]) if m["id"] == d.get('method_id')), None)
    if method is None or method["value"] not in PAYOUT_FIELDS:
        return json_error("That cashout method is not available.")
    amount = _parse_amount(d.get('amount'))
    cfg = current_app.config
    if amount is not None and 0 < amount < cfg["CASHOUT_MIN"]:
        return json_error(f"The minimum withdrawal is ${cfg['CASHOUT_MIN']:g}.", code="below_minimum", minimum=str(cfg["CASHOUT_MIN"]))
    if amount is None or not (cfg["CASHOUT_MIN"] <= amount <= cfg["CASHOUT_MAX"]):
        return json_error(f"Enter an amount between ${cfg['CASHOUT_MIN']:g} and ${cfg['CASHOUT_MAX']:g}.")
    address = str(d.get('address') or '').strip()
    if not (3 <= len(address) <= 200) or re.search(r'[\x00-\x1f]', address):
        return json_error(f"Enter your {PAYOUT_FIELDS[method['value']]}.")
    chime_name = str(d.get('chime_name') or '').strip()[:200]
    if method["value"] == "chime" and len(chime_name) < 2:
        return json_error("Enter the name on your Chime account.")

    cents = ledger.to_cents(amount)
    order = WithdrawalOrder(player_id=player.id, method_id=method["id"], method_value=method["value"],
                            method_name=method["name"], amount_cents=cents, address_enc=address,
                            chime_name=chime_name or None, idempotency_key=key, sandbox=payments.name == "sandbox")
    db.session.add(order)
    try:
        db.session.flush()
        ledger.debit(player.id, cents, 'withdrawal', 'withdrawal', order.id)  # hold the funds now
        audit("wallet.withdrawal_requested", target=str(order.id), detail={"amount_cents": cents, "method": method["value"]})
        db.session.commit()
    except ledger.InsufficientFunds:
        db.session.rollback()
        return json_error("Your wallet balance is too low for that cashout.", 402, code="insufficient_funds")
    except IntegrityError:
        db.session.rollback()
        prior = WithdrawalOrder.query.filter_by(player_id=player.id, idempotency_key=key).first()
        return jsonify(_withdrawal_view(prior)) if prior else json_error("Please try again.", 409)
    return jsonify(_withdrawal_view(order)), 201


@site_bp.route('/wallet/withdrawals/<int:wid>/cancel', methods=['POST'])
@player_required
def cancel_withdrawal(wid):
    player = current_player()
    claimed = (WithdrawalOrder.query.filter_by(id=wid, player_id=player.id, status='pending_review')
               .update({"status": "cancelled", "processed_at": utcnow()}, synchronize_session=False))
    if claimed != 1:
        db.session.rollback()
        return json_error("This cashout can no longer be cancelled.", 409)
    order = db.session.get(WithdrawalOrder, wid)
    ledger.credit(player.id, order.amount_cents, 'withdrawal_refund', 'withdrawal', order.id)
    audit("wallet.withdrawal_cancelled", target=str(wid))
    db.session.commit()
    return jsonify(_withdrawal_view(order))


@site_bp.route('/wallet/history')
@player_required
def wallet_history():
    pid = current_player().id
    from app.models_site import RedeemRequest
    redeems = RedeemRequest.query.filter_by(player_id=pid).order_by(RedeemRequest.id.desc()).limit(50).all()
    deposits = PaymentOrder.query.filter_by(player_id=pid).order_by(PaymentOrder.id.desc()).limit(50).all()
    cashouts = WithdrawalOrder.query.filter_by(player_id=pid).order_by(WithdrawalOrder.id.desc()).limit(50).all()
    entries = WalletEntry.query.filter_by(player_id=pid).order_by(WalletEntry.id.desc()).limit(50).all()
    return jsonify({
        "orders": sorted([_deposit_view(o) for o in deposits] + [_withdrawal_view(w) for w in cashouts]
                         + [{"id": r.id, "type": "redeem", "method": r.account.game.name, "amount": ledger.fmt(r.payout_cents),
                             "voided": ledger.fmt(r.void_cents) if r.void_cents else None, "status": r.status,
                             "sandbox": r.sandbox, "created_at": iso(r.created_at)} for r in redeems],
                         key=lambda x: x["created_at"], reverse=True)[:50],
        "ledger": [{"id": e.id, "kind": e.kind, "bucket": e.bucket, "amount": ledger.fmt(e.amount_cents),
                    "balance_after": ledger.fmt(e.balance_after_cents or 0), "created_at": iso(e.created_at)} for e in entries],
    })
