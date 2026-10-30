"""Turns what happens in the Telegram support group into chat state on the site.

process_update() is the single place that understands a Telegram update. It is called by the webhook endpoint
(routes/webhooks.py) and by the long-polling worker (telegram_poll.py), so both ways of receiving behave identically.
"""
import logging
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import ChatMessage, SupportChat
from app.services import chat_media, chat_team, telegram as tg
from app.utils.auth import utcnow

logger = logging.getLogger("jamesvault.chat_bridge")


def _mark_seen(chat_id, upto_id):
    from app.routes.site.chat import mark_seen
    mark_seen(chat_id, upto_id)


def _handle_callback(cb: dict) -> None:
    """A press on an Approve / Reject button under a cashout alert. Only trusted people may use them."""
    from app.models_site import WithdrawalOrder
    from app.services import withdrawals
    cid = cb.get("id")
    msg = cb.get("message") or {}
    user = cb.get("from") or {}
    data = str(cb.get("data") or "")
    parts = data.split(":")
    if (str((msg.get("chat") or {}).get("id")) != tg.group_id() or user.get("is_bot") or len(parts) != 3 or parts[0] != "wd"
            or not parts[2].isdigit()):
        tg.answer_callback(cid)
        return
    action, wid = parts[1], int(parts[2])
    if not tg.is_approver(user.get("id")):
        tg.answer_callback(cid, "Only the people allowed to handle cashouts can use these buttons.", alert=True)
        return
    who = user.get("first_name") or user.get("username") or "staff"
    order = db.session.get(WithdrawalOrder, wid)
    if order is None:
        tg.answer_callback(cid, "That cashout no longer exists.", alert=True)
        return
    if order.status != "pending_review" and action in ("ask", "yes", "reject", "back"):
        tg.answer_callback(cid, "This cashout was already handled.", alert=True)
        tg.refresh_withdrawal_alert_now(wid)
        return
    chat_id, message_id = msg["chat"]["id"], msg["message_id"]
    if action == "ask":       # one more tap before money moves
        tg.call("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id, "reply_markup": tg.confirm_keyboard(wid, order.amount_cents)})
        tg.answer_callback(cid, "Confirm to send the payout.")
    elif action == "back":
        tg.call("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id, "reply_markup": tg.withdrawal_keyboard(wid)})
        tg.answer_callback(cid)
    elif action == "yes":
        code, payload = withdrawals.approve(wid, actor_type="telegram", actor_id=user.get("id"), handled_by=who)
        status = payload.get("status")
        tg.answer_callback(cid, payload.get("error") if code != 200 else
                           "Payout sent to Paydora." if status in ("submitted", "completed") else
                           "Outcome unclear: check Paydora before doing anything else." if status == "needs_review" else
                           "Paydora refused it. The money was returned to the player.", alert=(code != 200 or status == "needs_review"))
    elif action == "reject":
        code, payload = withdrawals.reject(wid, actor_type="telegram", actor_id=user.get("id"), handled_by=who)
        tg.answer_callback(cid, "Rejected. The money was returned to the player." if code == 200 else payload.get("error"), alert=code != 200)
    else:
        tg.answer_callback(cid)


def process_update(update: dict) -> None:
    """Handle one Telegram update (a group message, a reaction or a button press). Never raises for content it does not care about."""
    if update.get("callback_query"):
        _handle_callback(update["callback_query"])
        return
    reaction = update.get("message_reaction")
    if reaction:  # a team member reacted to a player's message: the team has seen it (and everything before it)
        actor = reaction.get("user") or {}
        if str((reaction.get("chat") or {}).get("id")) == tg.group_id() and not actor.get("is_bot") and reaction.get("new_reaction"):
            chat_team.touch_presence()
            seen = ChatMessage.query.filter_by(sender='player', telegram_message_id=reaction.get("message_id")).first()
            if seen is not None:
                _mark_seen(seen.chat_id, seen.id)
            db.session.commit()
        return

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
        return  # not a reply we care about (other chat, General topic, a bot, a service message)

    chat = SupportChat.query.filter_by(telegram_topic_id=int(thread)).first()
    if chat is None:
        return
    if text.lower().split("@")[0] == "/typing":   # Telegram doesn't tell bots who is typing, so operators can send /typing
        chat.typing_until = utcnow() + timedelta(seconds=chat_team.TYPING_SECONDS)
        db.session.commit()
        return
    if text.startswith("/"):
        return
    if ChatMessage.query.filter_by(chat_id=chat.id, sender='operator', telegram_message_id=msg.get("message_id")).first():
        return  # Telegram re-delivered an update we already stored

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
    _mark_seen(chat.id, 10 ** 12)  # an answer means every earlier message was read
    try:
        db.session.commit()
    except IntegrityError:  # a racing duplicate delivery
        db.session.rollback()
