"""Live chat: the website talks to the support team through a Telegram supergroup (one topic per player)."""
import logging

import os

from flask import jsonify, request, send_from_directory
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import ChatMessage, SupportChat, iso
from app.services import chat_media, chat_team, telegram as tg
from app.utils.auth import current_player, json_error, player_required, rate_limit, utcnow

from . import site_bp

logger = logging.getLogger("jamesvault.chat")
MAX_LEN = 1000
PAGE = 100


def _view(m):
    return {"id": m.id, "sender": m.sender, "body": m.body,
            "operator": chat_team.display_name(m.operator_name) if m.sender == 'operator' else None, "created_at": iso(m.created_at),
            "kind": m.kind, "file": f"/api/v1/chat/files/{m.id}" if m.file_name else None}


def mark_seen(chat_id, upto_id):
    """The team has seen the player's messages up to this one (it replied or reacted): ticks turn blue."""
    ChatMessage.query.filter(ChatMessage.chat_id == chat_id, ChatMessage.sender == 'player', ChatMessage.id <= upto_id,
                             ChatMessage.seen_at.is_(None)).update({"seen_at": utcnow()}, synchronize_session=False)


def _seen_upto(chat):
    """Highest player message id the team has seen (0 = none). Seen is cumulative, so one number covers every earlier message."""
    if not chat:
        return 0
    return db.session.query(db.func.max(ChatMessage.id)).filter(ChatMessage.chat_id == chat.id, ChatMessage.sender == 'player',
                                                                 ChatMessage.seen_at.isnot(None)).scalar() or 0


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
        return jsonify({"enabled": False, "messages": [], "unread": 0, "seen_upto": 0, "online": False, "typing": False})
    player = current_player()
    chat = _chat_for(player)
    after = request.args.get('after', type=int) or 0
    msgs = []
    if chat:
        q = ChatMessage.query.filter(ChatMessage.chat_id == chat.id, ChatMessage.id > after)
        msgs = q.order_by(ChatMessage.id.desc()).limit(PAGE).all()[::-1] if not after else q.order_by(ChatMessage.id).limit(PAGE).all()
    typing = bool(chat and chat.typing_until and chat.typing_until > utcnow())
    return jsonify({"enabled": True, "messages": [_view(m) for m in msgs], "unread": _unread(chat), "seen_upto": _seen_upto(chat),
                    "online": chat_team.operators_online(), "typing": typing})


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


def _intro(player):
    """Who the player is: put at the top of the first message in a new topic, so operators know who they are talking to."""
    return (f"👤 <b>{tg.esc(player.username)}</b> ({tg.esc(player.email)}) · Player #{player.id}\n"
            "Reply in this topic and the player sees it on the website.\n\n")


def _ensure_topic(player, chat, force_new=False):
    """The player's topic in the group, created on first use. Returns (topic_id, created_now)."""
    if chat.telegram_topic_id and not force_new:
        return chat.telegram_topic_id, False
    topic = tg.create_topic(player.username)
    chat.telegram_topic_id = topic
    db.session.commit()
    return topic, True


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
        sent = _topic_send(player, chat, lambda topic, fresh: tg.send((_intro(player) if fresh else "") + f"💬 {tg.esc(text)}", thread_id=topic))
    except tg.TelegramError as e:
        logger.error("chat message not delivered to Telegram: %s", e.description)
        return json_error("We couldn't reach our support team just now. Please try again in a moment.", 502, code="chat_undelivered")

    msg = ChatMessage(chat_id=chat.id, sender='player', body=text, telegram_message_id=(sent or {}).get("message_id"))
    db.session.add(msg)
    chat.last_player_message_at = utcnow()
    db.session.commit()
    return jsonify(_view(msg)), 201


def _topic_send(player, chat, send):
    """Run send(thread_id) in the player's topic; if the topic was deleted in Telegram, make a new one and retry once."""
    topic, fresh = _ensure_topic(player, chat)
    try:
        return send(topic, fresh)
    except tg.TelegramError as e:
        if not tg.topic_is_gone(e):
            raise
        topic, _ = _ensure_topic(player, chat, force_new=True)   # the topic was deleted in Telegram: start a new one
        return send(topic, True)


@site_bp.route('/chat/attachments', methods=['POST'])
@player_required
@rate_limit('chat-attach', 10, 60)
def chat_attach():
    """A photo (up to 5 MB) or video (up to 20 MB) from the player, with an optional caption."""
    if not tg.configured():
        return json_error("Live chat isn't available yet.", 501, code="chat_unavailable")
    player = current_player()
    f = request.files.get('file')
    if f is None:
        return json_error("Choose a photo or video.")
    data = f.read(chat_media.VIDEO_MAX + 1)
    if not data:
        return json_error("That file is empty.")
    found = chat_media.sniff(data[:16])
    if found is None:
        return json_error("Send a photo (JPEG, PNG, WebP) or a video (MP4, MOV, WebM).")
    kind, ext, mime = found
    if len(data) > chat_media.limit_for(kind):
        return json_error(f"That {kind} is too large. The limit is {chat_media.limit_for(kind) // (1024 * 1024)} MB.", 413)
    caption = str(request.form.get('caption') or '').strip()[:MAX_LEN]

    chat = _chat_for(player)
    if chat is None:
        chat = SupportChat(player_id=player.id)
        db.session.add(chat)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            chat = _chat_for(player)
    label = f"💬 {tg.esc(caption)}" if caption else ""
    try:
        sent = _topic_send(player, chat, lambda t, fresh: tg.send_media(kind, data, f"upload.{ext}", mime,
                                                                           ((f"👤 <b>{tg.esc(player.username)}</b> · Player #{player.id}\n" if fresh else "") + label)[:1000], thread_id=t))
    except tg.TelegramError as e:
        logger.error("chat attachment not delivered to Telegram: %s", e.description)
        return json_error("We couldn't reach our support team just now. Please try again in a moment.", 502, code="chat_undelivered")

    name = chat_media.save(data, ext)
    msg = ChatMessage(chat_id=chat.id, sender='player', body=caption, kind=kind, file_name=name,
                      telegram_message_id=(sent or {}).get("message_id"))
    db.session.add(msg)
    chat.last_player_message_at = utcnow()
    db.session.commit()
    return jsonify(_view(msg)), 201


@site_bp.route('/chat/files/<int:mid>')
@player_required
def chat_file(mid):
    """A chat photo/video, only for the player whose conversation it belongs to."""
    msg = db.session.get(ChatMessage, mid)
    chat = _chat_for(current_player())
    if not msg or not msg.file_name or not chat or msg.chat_id != chat.id:
        return json_error("Not found", 404)
    ext = msg.file_name.rsplit(".", 1)[-1]
    mime = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "mp4": "video/mp4", "mov": "video/quicktime",
            "webm": "video/webm"}.get(ext)
    if mime is None or os.path.basename(msg.file_name) != msg.file_name:
        return json_error("Not found", 404)
    resp = send_from_directory(chat_media.chat_dir(), msg.file_name, mimetype=mime, conditional=True)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; media-src 'self'; img-src 'self'"
    return resp
