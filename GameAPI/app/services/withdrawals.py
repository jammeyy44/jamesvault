"""Approving and rejecting cashouts. One implementation used by the admin panel AND the Telegram buttons, so both behave identically.

Money safety (unchanged from the original admin flow):
  * approve first claims the order atomically (pending_review -> sending), so two staff members, a double tap, or the website and
    Telegram at the same moment can never send the payout twice;
  * the payout is requested at the provider (Paydora) with the idempotency key jv-wd-<id>;
  * a definite refusal refunds the held funds; an unclear outcome keeps them held for a person to reconcile (never retried blindly).
"""
from app import db
from app.models_site import Notification, Player, WithdrawalOrder
from app.services import telegram as tg, wallet as ledger
from app.services.payments import PaymentError, get_payments
from app.utils.auth import audit, utcnow


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


def approve(wid, actor_type=None, actor_id=None, handled_by=None):
    """Send a pending cashout to the payment provider, exactly once. Returns (http_status, payload)."""
    if not _claim(wid, 'pending_review', 'sending'):
        return 409, {"error": "This cashout has already been handled."}
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
        order.status = 'completed' if order.sandbox else 'submitted'
        if order.sandbox:
            order.processed_at = utcnow()
    except PaymentError as e:
        if e.definitive:  # the provider refused it: nothing was sent, give the money back
            order.status, order.note = 'failed', str(e)[:300]
            _refund(wid, 'failed', str(e)[:300])
        else:  # unknown outcome: keep the funds held and reconcile by hand; never retry blindly
            order.status = 'needs_review'
            order.note = "Provider outcome unknown. Check the provider dashboard, then resolve by hand."
    except Exception:
        order.status = 'needs_review'
        order.note = "Provider outcome unknown. Check the provider dashboard, then resolve by hand."
    audit("withdrawal.approve", target=str(wid), detail={"result": order.status}, actor_type=actor_type, actor_id=actor_id)
    tg.queue_withdrawal_refresh(db.session, wid, handled_by)
    db.session.commit()
    return 200, {"status": order.status, "note": order.note}
