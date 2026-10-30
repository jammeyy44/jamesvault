"""Approving and rejecting cashouts. One implementation used by the admin panel AND the Telegram buttons, so both behave identically.

Money safety (unchanged from the original admin flow):
  * approve first claims the order atomically (pending_review -> sending), so two staff members, a double tap, or the website and
    Telegram at the same moment can never send the payout twice;
  * the payout is requested at the provider (Paydora) with the idempotency key jv-wd-<id>;
  * a definite refusal refunds the held funds; an unclear outcome keeps them held for a person to reconcile (never retried blindly).
"""
import logging

from app import db
from app.models_site import Notification, Player, WithdrawalOrder
from app.services import telegram as tg, wallet as ledger
from app.services.payments import PaymentError, get_payments
from app.utils.auth import audit, utcnow


logger = logging.getLogger("jamesvault.withdrawals")


def _claim(order_id, from_status, to_status):
    n = WithdrawalOrder.query.filter_by(id=order_id, status=from_status).update({"status": to_status}, synchronize_session=False)
    db.session.commit()
    return n == 1


def _refund(order_id, final_status, note=None):
    order = db.session.get(WithdrawalOrder, order_id)
    order.processed_at, order.note = utcnow(), note
    ledger.credit(order.player_id, order.amount_cents, 'withdrawal_refund', 'withdrawal', order.id)
    db.session.add(Notification(player_id=order.player_id, title=f"Cashout {final_status}",
                                body=f"${ledger.fmt(order.amount_cents)} was returned to your wallet."))


def reject(wid, actor_type=None, actor_id=None, handled_by=None):
    """Reject a pending cashout and give the held money back. Returns (http_status, payload)."""
    if not _claim(wid, 'pending_review', 'rejected'):
        return 409, {"error": "This cashout has already been handled."}
    _refund(wid, 'rejected')
    audit("withdrawal.reject", target=str(wid), actor_type=actor_type, actor_id=actor_id)
    tg.queue_withdrawal_refresh(db.session, wid, handled_by)
    db.session.commit()
    return 200, {"status": "rejected"}


def approve(wid, actor_type=None, actor_id=None, handled_by=None, retry=False):
    """Send a pending cashout to the payment provider, exactly once. Returns (http_status, payload).

    retry=True re-sends an order that was left in 'sending' (the process stopped mid-way). It is safe because the provider
    de-duplicates on the idempotency key jv-wd-<id>: it replays the original order instead of creating a second one."""
    claimed = (_claim(wid, 'sending', 'sending') or _claim(wid, 'needs_review', 'sending')) if retry else _claim(wid, 'pending_review', 'sending')
    if not claimed:
        return 409, {"error": "This cashout cannot be sent from its current state." if retry else "This cashout has already been handled."}
    try:
        return _send(wid, actor_type, actor_id, handled_by)
    except Exception:
        # Whatever went wrong, never leave the order in 'sending' with the money held and nobody told.
        db.session.rollback()
        logger.exception("cashout %s: approval was interrupted", wid)
        order = db.session.get(WithdrawalOrder, wid)
        if order is not None and order.status == 'sending':
            order.status = 'needs_review'
            order.note = f"Approval was interrupted. Check Paydora (idempotency key jv-wd-{wid}), then retry or resolve by hand."
            tg.queue_withdrawal_refresh(db.session, wid, handled_by)
            db.session.commit()
        return 200, {"status": "needs_review", "note": order.note if order else None}


def _send(wid, actor_type, actor_id, handled_by):
    order = db.session.get(WithdrawalOrder, wid)
    payments = get_payments()
    if payments is None:
        order.status = 'pending_review'  # nothing was sent; put it back
        db.session.commit()
        return 501, {"error": "Payments are not enabled."}
    player = db.session.get(Player, order.player_id)
    try:
        resp = payments.create_withdrawal(method_id=order.method_id, amount=ledger.fmt(order.amount_cents),
                                          address=order.address_enc, user_name=player.username,
                                          chime_name=order.chime_name, idempotency_key=f"jv-wd-{order.id}")
        order.provider_withdrawal_id = resp.get("id")
        order.reference_id = resp.get("referenceId")
        logger.info("cashout %s sent to %s: provider id %s, reference %s", wid, getattr(payments, "name", "?"), order.provider_withdrawal_id, order.reference_id)
        order.status = 'completed' if order.sandbox else 'submitted'
        if order.sandbox:
            order.processed_at = utcnow()
    except PaymentError as e:
        why = f"{e} ({e.detail})" if getattr(e, "detail", None) else str(e)
        logger.warning("cashout %s was not accepted by the payment provider: %s", wid, why)
        if e.definitive:  # the provider refused it: nothing was sent, give the money back
            order.status, order.note = 'failed', why[:300]
            _refund(wid, 'failed', why[:300])
        else:  # unknown outcome: keep the funds held and reconcile by hand; never retry blindly
            order.status = 'needs_review'
            order.note = f"Provider outcome unknown ({e.detail or 'no answer'}). Check the provider dashboard, then retry or resolve by hand."[:300]
    except Exception:
        logger.exception("cashout %s: unexpected error while asking the payment provider", wid)
        order.status = 'needs_review'
        order.note = "Provider outcome unknown. Check the provider dashboard, then retry or resolve by hand."
    db.session.commit()   # the provider's answer is saved before anything else can fail
    result = {"status": order.status, "note": order.note}
    try:
        audit("withdrawal.approve", target=str(wid), detail={"result": result["status"]}, actor_type=actor_type, actor_id=actor_id)
        tg.queue_withdrawal_refresh(db.session, wid, handled_by)
        db.session.commit()
    except Exception:  # bookkeeping must never undo or hide a payout that already happened
        db.session.rollback()
        logger.exception("cashout %s: could not write the audit record (the payout result is saved)", wid)
        tg.queue_withdrawal_refresh(db.session, wid, handled_by)
        db.session.commit()
    return 200, result
