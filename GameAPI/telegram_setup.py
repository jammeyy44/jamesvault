"""
Telegram setup helper. Run from the GameAPI folder with the virtualenv active.

    python telegram_setup.py check                          # is the bot, the group and its Topics setting OK? (sends a test post)
    python telegram_setup.py webhook https://your-domain    # point Telegram at this site so operator replies reach the chat
    python telegram_setup.py info                           # what webhook Telegram currently has

Reads TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_ID and TELEGRAM_WEBHOOK_SECRET from GameAPI/.env. Never prints the token or secret.
"""
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROUP = os.getenv("TELEGRAM_GROUP_ID", "").strip()
SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()


def api(method, **payload):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=15)
    body = r.json()
    if not body.get("ok"):
        hint = ""
        if method == "setWebhook" and "resolve host" in (body.get("description") or ""):
            hint = ("
Telegram could not find that address on the internet. Use the exact public https address that reaches this API "
                    "(check it opens in a browser), or skip webhooks and run:  python telegram_poll.py  (no public address needed).")
        sys.exit(f"Telegram said no ({method}): {body.get('description')}{hint}")
    return body["result"]


def need(*names):
    missing = [n for n in names if not os.getenv(n, "").strip()]
    if missing:
        sys.exit("Missing in GameAPI/.env: " + ", ".join(missing))


def check():
    need("TELEGRAM_BOT_TOKEN", "TELEGRAM_GROUP_ID")
    me = api("getMe")
    print(f"Bot: @{me['username']} (ok)")
    chat = api("getChat", chat_id=GROUP)
    print(f"Group: {chat.get('title')!r}, type={chat.get('type')}")
    problems = []
    if chat.get("type") != "supergroup":
        problems.append("The group must be a supergroup (the id starts with -100).")
    if not chat.get("is_forum"):
        problems.append("Turn on Topics: Group settings > Topics.")
    member = api("getChatMember", chat_id=GROUP, user_id=me["id"])
    if member.get("status") != "administrator":
        problems.append("Make the bot an ADMIN of the group (it must also receive every message to see operator replies).")
    elif not member.get("can_manage_topics"):
        problems.append("Give the bot the 'Manage Topics' admin right.")
    if not SECRET:
        problems.append("Set TELEGRAM_WEBHOOK_SECRET in .env (any long random string).")
    if problems:
        print("\nFix these first:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    api("sendMessage", chat_id=GROUP, text="✅ StakeSweep bot connected. Live chat and deposit alerts are ready.")
    print("All good. A test message was posted in the group (General topic).")


def webhook(base):
    need("TELEGRAM_BOT_TOKEN", "TELEGRAM_GROUP_ID", "TELEGRAM_WEBHOOK_SECRET")
    if not base.startswith("https://"):
        sys.exit("Telegram only accepts an https:// address.")
    url = base.rstrip("/") + "/api/v1/webhooks/telegram"
    api("setWebhook", url=url, secret_token=SECRET, allowed_updates=["message", "message_reaction"], drop_pending_updates=False)
    print("Webhook set to", url)
    info()


def info():
    need("TELEGRAM_BOT_TOKEN")
    w = api("getWebhookInfo")
    print("Webhook url:", w.get("url") or "(none)")
    print("Pending updates:", w.get("pending_update_count"))
    if w.get("last_error_message"):
        print("Last delivery error:", w["last_error_message"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        check()
    elif cmd == "webhook" and len(sys.argv) == 3:
        webhook(sys.argv[2])
    elif cmd == "info":
        info()
    else:
        print(__doc__)
