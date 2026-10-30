"""Live chat: the website talks to the support team through a Telegram supergroup (one topic per player)."""
import logging

from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import ChatMessage, SupportChat, iso
from app.services import telegram as tg
from app.utils.auth import current_player, json_error, player_required, rate_limit, utcnow

from . import site_bp

logger = logging.getLogger("jamesvault.chat")
MAX_LEN = 1000
PAGE = 100


def _view(m):
    return {"id": m.id, "sender": m.sender, "body": m.body, "operator": m.operator_name, "created_at": iso(m.created_at)}


def _chat_for(player):
    return SupportChat.query.filter_by(player_id=player.id).first()


def _unread(chat):
    if not chat:
        return 0
    return ChatMessage.query.filter(ChatMessage.chat_id == chat.id, ChatMessage.sender == 'operator',
                                    ChatMessage.id > (chat.player_read_id or 0)).count()


@site_bp.route('/chat')
@player_required
def chat_state():
    """Messages (optionally only those after ?after=<id>) plus the unread count the floating icon shows."""
    if not tg.configured():
        return jsonify({"enabled": False, "messages": [], "unread": 0})
    player = current_player()
    chat = _chat_for(player)
    after = request.args.get('after', type=int) or 0
    msgs = []
    if chat:
        q = ChatMessage.query.filter(ChatMessage.chat_id == chat.id, ChatMessage.id > after)
        msgs = q.order_by(ChatMessage.id.desc()).limit(PAGE).all()[::-1] if not after else q.order_by(ChatMessage.id).limit(PAGE).all()
    return jsonify({"enabled": True, "messages": [_view(m) for m in msgs], "unread": _unread(chat)})


@site_bp.route('/chat/read', methods=['POST'])
@player_required
def chat_mark_read():
    chat = _chat_for(current_player())
    if chat:
        last = (db.session.query(db.func.max(ChatMessage.id)).filter(ChatMessage.chat_id == chat.id, ChatMessage.sender == 'operator').scalar() or 0)
        if last > (chat.player_read_id or 0):
            chat.player_read_id = last
            db.session.commit()
    return jsonify({"ok": True, "unread": 0})


def _ensure_topic(player, chat, force_new=False):
    """Create the player's topic in the group (once) and post a short header so operators know who they are talking to."""
    if chat.telegram_topic_id and not force_new:
        return chat.telegram_topic_id
    topic = tg.create_topic(player.username)
    chat.telegram_topic_id = topic
    db.session.commit()
    try:
        tg.send(f"👤 <b>{tg.esc(player.username)}</b> ({tg.esc(player.email)})\n🆔 Player #{player.id}\n"
                "Reply in this topic and the player sees it on the website.", thread_id=topic)
    except tg.TelegramError:
        logger.warning("could not post the topic header", exc_info=True)
    return topic


@site_bp.route('/chat/messages', methods=['POST'])
@player_required
@rate_limit('chat-send', 20, 60)
def chat_send():
    if not tg.configured():
        return json_error("Live chat isn't available yet.", 501, code="chat_unavailable")
    player = current_player()
    text = str((request.get_json(silent=True) or {}).get('text') or '').strip()
    if not text:
        return json_error("Type a message first.")
    if len(text) > MAX_LEN:
        return json_error(f"Messages can be up to {MAX_LEN} characters.")

    chat = _chat_for(player)
    if chat is None:
        chat = SupportChat(player_id=player.id)
        db.session.add(chat)
        try:
            db.session.commit()
        except IntegrityError:  # two first messages at once
            db.session.rollback()
            chat = _chat_for(player)

    try:
        topic = _ensure_topic(player, chat)
        try:
            sent = tg.send(f"💬 {tg.esc(text)}", thread_id=topic)
        except tg.TelegramError as e:
            if not tg.topic_is_gone(e):
                raise
            topic = _ensure_topic(player, chat, force_new=True)   # the topic was deleted in Telegram: start a new one
            sent = tg.send(f"💬 {tg.esc(text)}", thread_id=topic)
    except tg.TelegramError as e:
        logger.error("chat message not delivered to Telegram: %s", e.description)
        return json_error("We couldn't reach our support team just now. Please try again in a moment.", 502, code="chat_undelivered")

    msg = ChatMessage(chat_id=chat.id, sender='player', body=text, telegram_message_id=(sent or {}).get("message_id"))
    db.session.add(msg)
    chat.last_player_message_at = utcnow()
    db.session.commit()
    return jsonify(_view(msg)), 201
