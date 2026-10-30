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


def send(text: str, thread_id=None, html_mode=True):
    payload = {"chat_id": group_id(), "text": text[:4000], "disable_web_page_preview": True}
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
        if item["sync"]:
            _deliver(item)
        else:
            threading.Thread(target=_deliver, args=(item,), daemon=True).start()


@event.listens_for(Session, "after_rollback")
def _drop_pending(session):
    session.info.pop("tg_pending", None)
