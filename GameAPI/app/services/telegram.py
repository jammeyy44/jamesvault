"""
Telegram bridge: website live chat <-> a Telegram supergroup with topics, and deposit alerts to the same group.

  * Each player gets their own forum topic (named with their username). Their website messages are posted into it by the bot.
  * Anyone in the group who replies inside that topic is an operator; the webhook (routes/webhooks.py) stores the reply and the
    website shows it.
  * Deposit credits post a short summary into the group (optionally into a dedicated topic).

Configuration (GameAPI/.env, never committed):
    TELEGRAM_BOT_TOKEN       the bot token from @BotFather
    TELEGRAM_GROUP_ID        the supergroup id, e.g. -1001234567890
    TELEGRAM_WEBHOOK_SECRET  a long random string; Telegram sends it back on every webhook call
    TELEGRAM_DEPOSIT_TOPIC_ID (optional) topic id for deposit alerts; empty = the group's General topic
"""
import html
import logging
import threading

import requests
from flask import current_app
from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger("jamesvault.telegram")
API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 8
_http = requests.Session()  # one pooled connection: no new TLS handshake for every call (this is most of a send's latency)
_http.mount("https://", requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=16))


class TelegramError(Exception):
    def __init__(self, description, code=None):
        super().__init__(description)
        self.description, self.code = description, code


def _cfg(key, default=""):
    return str(current_app.config.get(key) or default).strip()


def configured() -> bool:
    return bool(_cfg("TELEGRAM_BOT_TOKEN") and _cfg("TELEGRAM_GROUP_ID"))


def group_id() -> str:
    return _cfg("TELEGRAM_GROUP_ID")


def _post(token, method, payload, files=None):
    """One Bot API call (multipart when `files` is given). Raises TelegramError with Telegram's own description.
    (Tests replace this function.)"""
    try:
        if files:
            resp = _http.post(API.format(token=token, method=method), data=payload, files=files, timeout=60)
        else:
            resp = _http.post(API.format(token=token, method=method), json=payload, timeout=TIMEOUT)
        body = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise TelegramError(f"Telegram unreachable ({type(e).__name__})") from e
    if not body.get("ok"):
        raise TelegramError(body.get("description") or "Telegram refused the request", body.get("error_code"))
    return body.get("result")


def call(method, payload):
    return _post(_cfg("TELEGRAM_BOT_TOKEN"), method, payload)


def create_topic(name: str) -> int:
    result = call("createForumTopic", {"chat_id": group_id(), "name": (name or "player")[:120]})
    return int(result["message_thread_id"])


def send(text: str, thread_id=None, html_mode=True, reply_markup=None):
    payload = {"chat_id": group_id(), "text": text[:4000], "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    if html_mode:
        payload["parse_mode"] = "HTML"
    return call("sendMessage", payload)


def send_media(kind, data: bytes, filename: str, mime: str, caption="", thread_id=None):
    """Post a photo or video into a topic."""
    method, field = ("sendPhoto", "photo") if kind == "photo" else ("sendVideo", "video")
    payload = {"chat_id": group_id()}
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    if caption:
        payload["caption"] = caption[:1000]
        payload["parse_mode"] = "HTML"
    if kind == "video":
        payload["supports_streaming"] = "true"
    return _post(_cfg("TELEGRAM_BOT_TOKEN"), method, payload, files={field: (filename, data, mime)})


def _download(token, file_path, max_bytes):
    """Fetch a file Telegram holds for the bot, refusing anything larger than max_bytes. (Tests replace this function.)"""
    try:
        with requests.get(f"https://api.telegram.org/file/bot{token}/{file_path}", stream=True, timeout=30) as resp:
            if resp.status_code != 200:
                raise TelegramError(f"download failed (HTTP {resp.status_code})")
            data = bytearray()
            for chunk in resp.iter_content(65536):
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise TelegramError("file too large")
            return bytes(data)
    except requests.RequestException as e:
        raise TelegramError(f"download failed ({type(e).__name__})") from e


def fetch_file(file_id: str, max_bytes: int) -> bytes:
    """Download a photo/video someone posted in the group (Bot API allows up to 20 MB)."""
    info = call("getFile", {"file_id": file_id})
    return _download(_cfg("TELEGRAM_BOT_TOKEN"), info["file_path"], max_bytes)


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def topic_is_gone(err: TelegramError) -> bool:
    d = (err.description or "").lower()
    return "thread not found" in d or "topic_deleted" in d or "topic deleted" in d or "topic_closed" in d


# ------------------------------------------------------------------ deposit alerts (sent only after the database commit)
def deposit_text(ref, username, email, amount_cents, method, sender=None, sandbox=False, status="Approved ✅") -> str:
    lines = [f"📋 Ref: {esc(ref)}", f"👤 User: {esc(username)} ({esc(email)})", f"💰 Amount: ${amount_cents / 100:,.2f}",
             f"💳 Method: {esc(method)}"]
    if sender:
        lines.append(f"🙍 Sender: {esc(sender)}")
    lines.append(f"📊 Status: {esc(status)}")
    if sandbox:
        lines.append("🧪 SANDBOX (test deposit, no real money)")
    return "\n".join(lines)


def queue_deposit_alert(session, **fields):
    """Remember a deposit alert on the session; it is sent when (and only if) the transaction commits."""
    if not configured():
        return
    session.info.setdefault("tg_pending", []).append({
        "token": _cfg("TELEGRAM_BOT_TOKEN"), "chat": group_id(), "topic": _cfg("TELEGRAM_DEPOSIT_TOPIC_ID"),
        "text": deposit_text(**fields), "sync": bool(current_app.config.get("TELEGRAM_SYNC")),
    })


# ------------------------------------------------------------------ cashout requests: alert with Approve / Reject buttons
WD_HEADLINE = {
    "pending_review": "Pending review ⏳", "sending": "Sending… ⏳", "submitted": "Approved ✅ (sent to Paydora)",
    "completed": "Completed ✅", "rejected": "Rejected ❌", "cancelled": "Cancelled by the player", "failed": "Failed ❌ (money returned to the player)",
    "needs_review": "Needs review ⚠️ (check Paydora)", "failed_at_provider": "Failed at the provider ⚠️", "credited_back": "Credited back ↩",
}


def withdrawal_text(order, player, handled_by=None) -> str:
    lines = [f"📋 Ref: WD-{order.id}", f"👤 User: {esc(player.username)} ({esc(player.email)})", f"💰 Amount: ${order.amount_cents / 100:,.2f}",
             f"💳 Method: {esc(order.method_name)}", f"📍 Send to: {esc(order.address_enc)}"]
    if order.chime_name:
        lines.append(f"🙍 Name on account: {esc(order.chime_name)}")
    lines.append(f"📊 Status: {esc(WD_HEADLINE.get(order.status, order.status))}")
    if handled_by and order.status != "pending_review":
        lines.append(f"🧑\u200d💼 By: {esc(handled_by)}")
    if order.sandbox:
        lines.append("🧪 SANDBOX (test cashout, no real money)")
    return "\n".join(lines)


def withdrawal_keyboard(wid):
    return {"inline_keyboard": [[{"text": "✅ Approve", "callback_data": f"wd:ask:{wid}"}, {"text": "❌ Reject", "callback_data": f"wd:reject:{wid}"}]]}


def confirm_keyboard(wid, amount_cents):
    return {"inline_keyboard": [[{"text": f"✅ Yes, send ${amount_cents / 100:,.2f}", "callback_data": f"wd:yes:{wid}"},
                                 {"text": "↩ Back", "callback_data": f"wd:back:{wid}"}]]}


def answer_callback(callback_id, text="", alert=False):
    try:
        call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:190], "show_alert": alert})
    except TelegramError:
        logger.warning("could not answer a callback", exc_info=True)


def is_approver(user_id) -> bool:
    """Only people trusted with money may press the buttons: the listed ids, or (when none are listed) the group's admins."""
    allowed = [x.strip() for x in _cfg("TELEGRAM_APPROVER_IDS").split(",") if x.strip()]
    if allowed:
        return str(user_id) in allowed
    try:
        member = call("getChatMember", {"chat_id": group_id(), "user_id": user_id})
    except TelegramError:
        return False
    return member.get("status") in ("creator", "administrator")


def _run_async(fn, *args):
    """Run fn(*args) in its own thread with its own app context and database session (it must not touch the committing
    session). With TELEGRAM_SYNC set (tests) the caller waits for it to finish so results are deterministic."""
    from app import db
    wait = bool(current_app.config.get("TELEGRAM_SYNC"))
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            try:
                fn(*args)
            except Exception:
                logger.warning("telegram cashout alert failed", exc_info=True)
            finally:
                db.session.remove()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    if wait:
        t.join(timeout=15)


def _post_withdrawal_alert(wid):
    from app import db
    from app.models_site import Player, WithdrawalOrder
    order = db.session.get(WithdrawalOrder, wid)
    if order is None or not configured():
        return
    player = db.session.get(Player, order.player_id)
    topic = _cfg("TELEGRAM_WITHDRAWAL_TOPIC_ID") or None
    sent = send(withdrawal_text(order, player), thread_id=topic,
                reply_markup=withdrawal_keyboard(wid) if order.status == "pending_review" else None)
    order.telegram_message_id = (sent or {}).get("message_id")
    db.session.commit()


def refresh_withdrawal_alert_now(wid, handled_by=None):
    """Edit the group message to the order's current status (and drop the buttons once it is no longer pending)."""
    from app import db
    from app.models_site import Player, WithdrawalOrder
    order = db.session.get(WithdrawalOrder, wid)
    if order is None or not order.telegram_message_id or not configured():
        return
    player = db.session.get(Player, order.player_id)
    markup = withdrawal_keyboard(wid) if order.status == "pending_review" else {"inline_keyboard": []}
    try:
        call("editMessageText", {"chat_id": group_id(), "message_id": int(order.telegram_message_id), "text": withdrawal_text(order, player, handled_by)[:4000],
                                 "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": markup})
    except TelegramError as e:
        if "not modified" not in (e.description or "").lower():
            logger.warning("could not update the cashout alert: %s", e.description)


def queue_withdrawal_alert(session, wid):
    if configured():
        session.info.setdefault("tg_pending", []).append({"kind": "wd_alert", "wid": wid})


def queue_withdrawal_refresh(session, wid, handled_by=None):
    if configured():
        session.info.setdefault("tg_pending", []).append({"kind": "wd_refresh", "wid": wid, "handled_by": handled_by})


def _deliver(item):
    payload = {"chat_id": item["chat"], "text": item["text"][:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    if item["topic"]:
        payload["message_thread_id"] = int(item["topic"])
    try:
        _post(item["token"], "sendMessage", payload)
    except Exception:  # an alert must never affect the deposit itself
        logger.warning("could not post the deposit alert to Telegram", exc_info=True)


@event.listens_for(Session, "after_commit")
def _send_pending(session):
    for item in session.info.pop("tg_pending", []) or []:
        if item.get("kind") == "wd_alert":
            _run_async(_post_withdrawal_alert, item["wid"])
            continue
        if item.get("kind") == "wd_refresh":
            _run_async(refresh_withdrawal_alert_now, item["wid"], item.get("handled_by"))
            continue
        if item["sync"]:
            _deliver(item)
        else:
            threading.Thread(target=_deliver, args=(item,), daemon=True).start()


@event.listens_for(Session, "after_rollback")
def _drop_pending(session):
    session.info.pop("tg_pending", None)
