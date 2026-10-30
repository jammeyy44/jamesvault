"""
Receive Telegram updates by long polling. Use this INSTEAD of the webhook when the API has no public https address
(or while the domain/SSL is not ready): it needs nothing but outbound internet access, and replies arrive within a second.

    python telegram_poll.py

Run it as a service (see the README) and run only ONE copy. It switches the bot to polling mode (removes any webhook).
To go back to a webhook later: python telegram_setup.py webhook https://your-domain
"""
import logging
import time

import requests

from app import app, db
from app.services import chat_bridge, telegram as tg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("telegram_poll")
WAIT = 25  # seconds Telegram holds each request open when nothing is new


def main():
    with app.app_context():
        if not tg.configured():
            raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_GROUP_ID in GameAPI/.env first.")
        token = app.config["TELEGRAM_BOT_TOKEN"].strip()
        base = tg.API.format(token=token, method="")
        requests.post(base + "deleteWebhook", json={"drop_pending_updates": False}, timeout=15)   # polling and webhooks are exclusive
        log.info("Polling Telegram for the support group. Press Ctrl+C to stop.")
        offset = None
        while True:
            try:
                payload = {"timeout": WAIT, "allowed_updates": ["message", "message_reaction"]}
                if offset is not None:
                    payload["offset"] = offset
                body = requests.post(base + "getUpdates", json=payload, timeout=WAIT + 10).json()
                if not body.get("ok"):
                    log.error("Telegram refused getUpdates: %s", body.get("description"))
                    time.sleep(5)
                    continue
                for update in body.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        chat_bridge.process_update(update)
                    except Exception:  # one bad update must never stop the worker
                        db.session.rollback()
                        log.exception("could not process update %s", update.get("update_id"))
                    finally:
                        db.session.remove()
            except requests.RequestException as e:
                log.warning("network problem (%s); retrying in 3s", type(e).__name__)
                time.sleep(3)


if __name__ == "__main__":
    main()
