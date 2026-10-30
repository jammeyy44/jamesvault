"""
Payment provider webhooks (no CSRF/session: authenticity is the HMAC signature).

Rules from the provider docs, implemented here:
  * verify X-Signature = "sha256=" + HMAC-SHA256(raw body, whsec_...) in constant time BEFORE parsing;
  * respond 2xx fast; at-least-once + unordered delivery -> deduplicate on deliveryId and make every
    wallet movement idempotent;
  * drive logic from `event`, and never trust memo/userName text from third parties.
A deposit is credited only for an order WE created, after re-querying the provider to confirm it is paid.
"""
import hashlib
from datetime import timedelta
import hmac
import json
import logging

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import ChatMessage, Notification, PaymentOrder, Player, SupportChat, WebhookDelivery, WithdrawalOrder
from app.services import bonus, telegram as tg, wallet as ledger
from app.services.payments import PaymentError, get_payments
from app.utils.auth import audit, utcnow

logger = logging.getLogger("jamesvault.webhooks")
hooks_bp = Blueprint('hooks', __name__, url_prefix='/api/v1/webhooks')

PAID_STATUSES = {"paid", "partial_paid", "paid_with_remarks", "repair_order_success", "in_game_paid"}
FAILED_STATUSES = {"failed", "expired", "cancelled"}


def _verify(raw: bytes) -> bool:
    secret = current_app.config.get("PAYDORA_WEBHOOK_SECRET", "")
    if not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    given = request.headers.get("X-Signature", "")
    return len(given) == len(expected) and hmac.compare_digest(given, expected)


def _notify(player_id, title, body=None):
    db.session.add(Notification(player_id=player_id, title=title, body=body))


def _cents(value):
    try:
        return ledger.to_cents(value)
    except Exception:
        return None


@hooks_bp.route('/paydora', methods=['POST'])
def paydora():
    raw = request.get_data()  # raw bytes: re-serialising parsed JSON would change them
    if not current_app.config.get("PAYDORA_WEBHOOK_SECRET"):
        return jsonify({"error": "Webhooks are not configured"}), 503
    if not _verify(raw):
        logger.warning("webhook rejected: bad signature")
        return jsonify({"error": "Invalid signature"}), 401
    try:
        payload = json.loads(raw)
        event, data, delivery_id = payload["event"], payload["data"], str(payload["deliveryId"])
    except (ValueError, KeyError, TypeError):
        return jsonify({"error": "Malformed payload"}), 400

    if WebhookDelivery.query.filter_by(delivery_id=delivery_id).first():
        return jsonify({"ok": True, "duplicate": True})  # retries are expected: acknowledge, apply nothing

    delivery = WebhookDelivery(delivery_id=delivery_id, event=str(event)[:40])
    db.session.add(delivery)
    try:
        status = _handle(event, data, delivery)
        if status:
            db.session.rollback()
            return jsonify({"error": "Try again later"}), status  # provider retries 1/5/30/120 min
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # a concurrent duplicate delivery won the race
        return jsonify({"ok": True, "duplicate": True})
    return jsonify({"ok": True})


def _handle(event, data, delivery):
    """Returns an HTTP status to make the provider retry (e.g. 503), or None when processed."""
    if event.startswith("deposit."):
        dep_id = str(data.get("depositId") or "")
        delivery.external_id = dep_id[:40]
        order = PaymentOrder.query.filter_by(provider_deposit_id=dep_id).first() if dep_id else None

        if event == "deposit.paid":
            if order is None:
                # Not an order we created (e.g. direct-pay Chime). Never auto-credit from a memo: park it for staff.
                delivery.handled, delivery.credited = False, False
                delivery.amount_cents = _cents(data.get("paidAmount") or data.get("amount"))
                delivery.memo = (str(data.get("memo") or "")[:200]) or None
                delivery.summary = f"Unmatched deposit {dep_id} amount={data.get('amount')} chime={bool(data.get('isChimney'))}"[:400]
                return None
            payments = get_payments()
            try:  # defence in depth: confirm with the provider before crediting
                verified = payments.get_deposit(dep_id) if payments else None
            except PaymentError:
                return 503
            if not verified or verified.get("status") not in PAID_STATUSES:
                delivery.handled, delivery.summary = False, f"deposit.paid not confirmed by provider ({(verified or {}).get('status')})"
                return None
            cents = _cents(verified.get("paidAmount") or verified.get("amount"))
            if not cents or cents <= 0:
                delivery.handled, delivery.summary = False, "paid amount unreadable"
                return None
            if ledger.credit(order.player_id, cents, 'deposit', 'payment_order', order.id):
                order.status, order.paid_at = 'paid', utcnow()
                if order.amount_cents != cents:
                    order.note = f"Credited {ledger.fmt(cents)} (provider-reported amount)"
                    order.amount_cents = cents
                extra = bonus.grant_deposit_bonus(order)
                _notify(order.player_id, "Deposit received", f"${ledger.fmt(cents)} was added to your wallet."
                        + (f" Plus ${ledger.fmt(extra)} Deposit Boost bonus." if extra else ""))
                _deposit_alert(order, cents)
                audit("wallet.deposit_credited", target=str(order.id), actor_type="system",
                      detail={"cents": cents, "delivery": delivery.delivery_id})
                delivery.credited = True
            delivery.handled = True
            return None

        if event == "deposit.failed":
            if order and order.status == 'pending':
                order.status = 'failed'
            delivery.handled = True
            return None

        if event == "deposit.refunded":
            delivery.handled = True
            if order is None:
                delivery.handled, delivery.summary = False, f"refund for unknown deposit {dep_id}"
                return None
            cents = _cents(data.get("refundAmount") or data.get("amount"))
            if cents and cents > 0 and order.status in ('paid', 'refunded'):
                # Recorded even if the player already spent it (balance may go negative: staff follow up).
                if ledger.debit(order.player_id, cents, 'refund', 'payment_order', order.id, allow_negative=True):
                    order.status = 'refunded'
                    bonus.reverse_deposit_bonus(order, cents, order.amount_cents)
                    _notify(order.player_id, "Deposit refunded", f"${ledger.fmt(cents)} was taken back by the payment provider.")
                    audit("wallet.deposit_refunded", target=str(order.id), actor_type="system", detail={"cents": cents})
            return None
        delivery.handled = True
        return None

    if event.startswith("withdrawal."):
        wid = str(data.get("withdrawalId") or "")
        delivery.external_id = wid[:40]
        w = WithdrawalOrder.query.filter_by(provider_withdrawal_id=wid).first() if wid else None
        delivery.handled = True
        if w is None:
            delivery.handled, delivery.summary = False, f"{event} for unknown withdrawal {wid}"
            return None
        if event == "withdrawal.completed":
            if w.status in ('submitted', 'sending', 'needs_review', 'failed_at_provider'):
                w.status, w.processed_at = 'completed', utcnow()
                _notify(w.player_id, "Cashout sent", f"${ledger.fmt(w.amount_cents)} via {w.method_name}.")
        elif event == "withdrawal.cancelled":
            if w.status in ('submitted', 'sending', 'needs_review'):
                w.status, w.processed_at = 'cancelled', utcnow()
                ledger.credit(w.player_id, w.amount_cents, 'withdrawal_refund', 'withdrawal', w.id)  # nothing was paid
                _notify(w.player_id, "Cashout cancelled", f"${ledger.fmt(w.amount_cents)} was returned to your wallet.")
        elif event == "withdrawal.failed_at_provider":
            # Sent but the player never received it; the provider returned it to the merchant. Staff decide how to make it right.
            w.status, w.note = 'failed_at_provider', "Sent but not received by the player. Staff will follow up."
            delivery.handled = False
            delivery.summary = f"Withdrawal {w.id} failed at provider: review and credit back or re-send"
        return None

    delivery.handled = False
    delivery.summary = f"unhandled event {event}"[:400]
    return None


def _deposit_alert(order, cents):
    """Queue the Telegram deposit alert; it is sent only if the surrounding transaction commits."""
    player = db.session.get(Player, order.player_id)
    if player is None:
        return
    tg.queue_deposit_alert(db.session, ref=order.reference_id or f"DEP-{order.id}", username=player.username, email=player.email,
                           amount_cents=cents, method=order.method_name, sandbox=bool(order.sandbox))


# ---------------------------------------------------------------- Telegram: replies from the support group
@hooks_bp.route('/telegram', methods=['POST'])
def telegram_webhook():
    """Telegram calls this for every message in the support group. Authentic only if the secret header matches.
    A message inside a player's topic from a (non-bot) group member is that player's operator reply."""
    secret = str(current_app.config.get("TELEGRAM_WEBHOOK_SECRET") or "")
    if not secret or not tg.configured():
        return jsonify({"error": "not configured"}), 503
    given = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(given.encode(), secret.encode()):
        return jsonify({"error": "forbidden"}), 403

    from app.routes.site.chat import mark_seen
    from app.services import chat_media, chat_team

    update = request.get_json(silent=True) or {}
    reaction = update.get("message_reaction")
    if reaction:  # a team member reacted to a player's message: the team has seen it (and everything before it)
        actor = reaction.get("user") or {}
        if (str((reaction.get("chat") or {}).get("id")) == tg.group_id() and not actor.get("is_bot") and reaction.get("new_reaction")):
            chat_team.touch_presence()
            seen = ChatMessage.query.filter_by(sender='player', telegram_message_id=reaction.get("message_id")).first()
            if seen is not None:
                mark_seen(seen.chat_id, seen.id)
            db.session.commit()
        return jsonify({"ok": True})

    msg = update.get("message") or {}
    sender = msg.get("from") or {}
    text = (msg.get("text") or msg.get("caption") or "").strip()
    photo, video = (msg.get("photo") or [None])[-1], msg.get("video")
    has_media = any(k in msg for k in ("photo", "document", "video", "voice", "sticker", "audio", "video_note", "animation"))
    thread = msg.get("message_thread_id")
    in_group = str((msg.get("chat") or {}).get("id")) == tg.group_id() and not sender.get("is_bot")
    if in_group and (text or has_media):          # anyone on the team writing anywhere in the group means the team is around
        chat_team.touch_presence()
        db.session.commit()
    if not in_group or not thread or not (text or has_media):
        return jsonify({"ok": True})  # not a reply we care about (other chat, General topic, a bot, a service message)

    chat = SupportChat.query.filter_by(telegram_topic_id=int(thread)).first()
    if chat is None:
        return jsonify({"ok": True})
    if text.lower().split("@")[0] == "/typing":   # Telegram doesn't tell bots who is typing, so operators can send /typing
        chat.typing_until = utcnow() + timedelta(seconds=chat_team.TYPING_SECONDS)
        db.session.commit()
        return jsonify({"ok": True})
    if text.startswith("/"):
        return jsonify({"ok": True})
    if ChatMessage.query.filter_by(chat_id=chat.id, sender='operator', telegram_message_id=msg.get("message_id")).first():
        return jsonify({"ok": True})              # Telegram re-delivered an update we already stored

    kind, file_name, body = 'text', None, text
    media = photo or video
    if media:
        try:
            if (media.get("file_size") or 0) > chat_media.VIDEO_MAX:
                raise tg.TelegramError("file too large")
            data = tg.fetch_file(media["file_id"], chat_media.VIDEO_MAX)
            found = chat_media.sniff(data[:16])
            if found is None:
                raise tg.TelegramError("unsupported file type")
            kind, ext, _mime = found
            file_name = chat_media.save(data, ext)
        except (tg.TelegramError, KeyError):
            logger.warning("could not fetch an operator attachment", exc_info=True)
            body = (text + chr(10) if text else "") + "📎 The support team sent an attachment that can't be shown here."
    elif not text:
        body = "📎 The support team sent an attachment that can't be shown here."
    alias = chat_team.alias_for(sender.get("id"))   # players only ever see "Operator N", never the real name
    db.session.add(ChatMessage(chat_id=chat.id, sender='operator', body=body[:2000], operator_name=alias, kind=kind,
                               file_name=file_name, telegram_message_id=msg.get("message_id")))
    chat.typing_until = None
    mark_seen(chat.id, 10 ** 12)  # an answer means every earlier message was read
    try:
        db.session.commit()
    except IntegrityError:  # a racing duplicate delivery
        db.session.rollback()
    return jsonify({"ok": True})
