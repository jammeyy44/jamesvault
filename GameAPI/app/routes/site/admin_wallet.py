"""Admin: cashout review, deposit orders, unmatched payments, payment-method presentation. Superadmin only."""
from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import (
    Notification, PaymentMethodSetting, PaymentOrder, Player, WebhookDelivery, WithdrawalOrder, iso,
)
from app.services import bonus, telegram as tg, wallet as ledger, withdrawals
from app.services.payments import PaymentError, get_payments
from app.utils.auth import admin_required, audit, json_error, utcnow

from . import site_bp

A = '/admin'


def _body():
    return request.get_json(silent=True) or {}


def _notify(pid, title, body=None):
    db.session.add(Notification(player_id=pid, title=title, body=body))


def _names(ids):
    return {p.id: p.username for p in Player.query.filter(Player.id.in_(set(ids) or [0]))}


# ---------------------------------------------------------------- cashouts
@site_bp.route(f'{A}/withdrawals')
@admin_required()
def admin_withdrawals():
    q = WithdrawalOrder.query
    if request.args.get('status'):
        q = q.filter(WithdrawalOrder.status.in_(request.args['status'].split(',')))
    rows = q.order_by(WithdrawalOrder.id.desc()).limit(200).all()
    names = _names(r.player_id for r in rows)
    return jsonify({"items": [{
        "id": r.id, "player": names.get(r.player_id), "method": r.method_name, "amount": ledger.fmt(r.amount_cents),
        "destination": r.address_enc, "chime_name": r.chime_name, "status": r.status, "sandbox": r.sandbox, "reference": r.reference_id,
        "note": r.note, "created_at": iso(r.created_at)} for r in rows]})


def _claim(order_id, from_status, to_status):
    n = (WithdrawalOrder.query.filter_by(id=order_id, status=from_status)
         .update({"status": to_status}, synchronize_session=False))
    db.session.commit()
    return n == 1


@site_bp.route(f'{A}/withdrawals/<int:wid>', methods=['PATCH'])
@admin_required()
def admin_withdrawal_update(wid):
    """approve: send the payout exactly once. reject: refund the held funds. credit_back: return funds after the provider
    reported failed_at_provider. resolve_completed / resolve_failed: reconcile a needs_review payout by hand."""
    action = _body().get('action')
    w = db.session.get(WithdrawalOrder, wid)
    if not w or action not in ('approve', 'reject', 'credit_back', 'resolve_completed', 'resolve_failed'):
        return json_error("Invalid request")

    def refund(final_status, note=None):
        order = db.session.get(WithdrawalOrder, wid)
        order.processed_at, order.note = utcnow(), note
        ledger.credit(order.player_id, order.amount_cents, 'withdrawal_refund', 'withdrawal', order.id)
        _notify(order.player_id, f"Cashout {final_status}", f"${ledger.fmt(order.amount_cents)} was returned to your wallet.")

    if action == 'reject':
        code, payload = withdrawals.reject(wid)
        return jsonify(payload), code

    if action == 'credit_back':
        if not _claim(wid, 'failed_at_provider', 'credited_back'):
            return json_error("Only payouts that failed at the provider can be credited back.", 409)
        refund('credited back', "Returned after the payout did not reach you.")
        audit("withdrawal.credit_back", target=str(wid))
        tg.queue_withdrawal_refresh(db.session, wid)
        db.session.commit()
        return jsonify({"status": "credited_back"})

    if action in ('resolve_completed', 'resolve_failed'):
        if not _claim(wid, 'needs_review', 'completed' if action == 'resolve_completed' else 'failed'):
            return json_error("Only payouts needing review can be resolved.", 409)
        if action == 'resolve_failed':
            refund('failed', "Reconciled by staff: not sent.")
        else:
            order = db.session.get(WithdrawalOrder, wid)
            order.processed_at, order.note = utcnow(), "Reconciled by staff: sent."
        audit("withdrawal.resolve", target=str(wid), detail={"action": action})
        tg.queue_withdrawal_refresh(db.session, wid)
        db.session.commit()
        return jsonify({"status": "completed" if action == 'resolve_completed' else 'failed'})

    # approve: the shared service claims the order atomically, so two admins (or Telegram and the site) can never send it twice
    code, payload = withdrawals.approve(wid)
    return jsonify(payload), code


# ---------------------------------------------------------------- deposits + unmatched payments
@site_bp.route(f'{A}/payments')
@admin_required()
def admin_payments():
    rows = PaymentOrder.query.order_by(PaymentOrder.id.desc()).limit(200).all()
    names = _names(r.player_id for r in rows)
    return jsonify({"items": [{
        "id": r.id, "player": names.get(r.player_id), "method": r.method_name, "amount": ledger.fmt(r.amount_cents),
        "status": r.status, "sandbox": r.sandbox, "reference": r.reference_id, "note": r.note,
        "created_at": iso(r.created_at)} for r in rows]})


@site_bp.route(f'{A}/unmatched-payments')
@admin_required()
def admin_unmatched():
    rows = WebhookDelivery.query.filter_by(handled=False).order_by(WebhookDelivery.id.desc()).limit(100).all()
    return jsonify({"items": [{
        "id": r.id, "event": r.event, "external_id": r.external_id,
        "amount": ledger.fmt(r.amount_cents) if r.amount_cents else None,
        "memo": r.memo, "summary": r.summary, "credited": r.credited, "created_at": iso(r.created_at)} for r in rows]})


@site_bp.route(f'{A}/unmatched-payments/<int:did>', methods=['PATCH'])
@admin_required()
def admin_unmatched_resolve(did):
    """credit: staff verified who paid and credit that player (once). dismiss: nothing to do."""
    d = _body()
    row = db.session.get(WebhookDelivery, did)
    if not row or d.get('action') not in ('credit', 'dismiss') or row.handled:
        return json_error("Invalid request")
    if d['action'] == 'credit':
        player = Player.query.filter_by(username=str(d.get('username') or '').strip()).first()
        if not player or not row.amount_cents or row.event != 'deposit.paid' or not row.external_id:
            return json_error("Needs a valid username and a paid deposit.")
        try:
            ok = ledger.credit(player.id, row.amount_cents, 'deposit', 'webhook_deposit', row.external_id)
        except IntegrityError:
            db.session.rollback()
            ok = False
        if not ok:
            return json_error("This payment was already credited.", 409)
        row.credited = True
        bonus.grant_referral_bonus(player.id, row.amount_cents)
        _notify(player.id, "Deposit received", f"${ledger.fmt(row.amount_cents)} was added to your wallet.")
        tg.queue_deposit_alert(db.session, ref=row.external_id, username=player.username, email=player.email,
                               amount_cents=row.amount_cents, method="Direct payment (matched by staff)")
        audit("wallet.manual_credit", target=str(did), detail={"player": player.id, "cents": row.amount_cents})
    else:
        audit("wallet.unmatched_dismissed", target=str(did))
    row.handled = True
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- method presentation (badges are admin-entered text)
@site_bp.route(f'{A}/payment-methods')
@admin_required()
def admin_method_settings():
    return jsonify({"items": [s.to_dict() for s in PaymentMethodSetting.query.order_by(PaymentMethodSetting.sort_order)]})


@site_bp.route(f'{A}/payment-methods', methods=['POST'])
@admin_required()
def admin_method_setting_save():
    d = _body()
    value = "".join(ch for ch in str(d.get('value') or '').lower() if ch.isalnum())
    if not value:
        return json_error("Method value is required (e.g. cashapp, chime).")
    s = PaymentMethodSetting.query.filter_by(value=value).first() or PaymentMethodSetting(value=value)
    s.label = (d.get('label') or '').strip()[:60] or None
    s.badge = (d.get('badge') or '').strip()[:30] or None
    s.badge_tone = d.get('badge_tone') if d.get('badge_tone') in ('green', 'amber', 'red', 'blue') else 'green'
    s.is_enabled = bool(d.get('is_enabled', True))
    s.sort_order = int(d.get('sort_order') or 0)
    db.session.add(s)
    audit("payment_method.save", target=value)
    db.session.commit()
    return jsonify(s.to_dict())


@site_bp.route(f'{A}/payment-methods/<int:sid>', methods=['DELETE'])
@admin_required()
def admin_method_setting_delete(sid):
    s = db.session.get(PaymentMethodSetting, sid)
    if not s:
        return json_error("Not found", 404)
    db.session.delete(s)
    audit("payment_method.delete", target=s.value)
    db.session.commit()
    return jsonify({"ok": True})
