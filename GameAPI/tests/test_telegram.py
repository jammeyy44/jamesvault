"""Telegram bridge: website live chat <-> support group topics, and deposit alerts. Telegram itself is faked."""
import pytest

from app import db
from app.models_site import ChatMessage, Player, SupportChat
from app.services import telegram as tg

SECRET = "whsec-telegram-test"
GROUP = "-1001234567890"


class FakeTelegram:
    def __init__(self):
        self.calls, self.fail_next = [], []   # fail_next: queue of TelegramError to raise on the next sendMessage calls
        self.down = False
        self._topic = 100
        self._msg = 500

    def __call__(self, token, method, payload):
        if self.down:
            raise tg.TelegramError("Telegram unreachable (ConnectionError)")
        self.calls.append((method, dict(payload)))
        if method == "createForumTopic":
            self._topic += 1
            return {"message_thread_id": self._topic}
        if method == "sendMessage":
            if self.fail_next:
                raise self.fail_next.pop(0)
            self._msg += 1
            return {"message_id": self._msg}
        raise AssertionError(method)

    def sent(self):
        return [p for m, p in self.calls if m == "sendMessage"]


@pytest.fixture()
def telegram(app, monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(tg, "_post", fake)
    for k, v in {"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_GROUP_ID": GROUP, "TELEGRAM_WEBHOOK_SECRET": SECRET,
                 "TELEGRAM_DEPOSIT_TOPIC_ID": "", "TELEGRAM_SYNC": True}.items():
        monkeypatch.setitem(app.config, k, v)
    return fake


def _reply(api, thread, text="Hello from support", message_id=900, first="Alex", chat=GROUP, bot=False, secret=SECRET, **extra):
    msg = {"message_id": message_id, "from": {"id": 5, "is_bot": bot, "first_name": first}, "chat": {"id": int(chat)},
           "message_thread_id": thread, "text": text, **extra}
    return api.c.post('/api/v1/webhooks/telegram', json={"update_id": 1, "message": msg},
                           headers={"X-Telegram-Bot-Api-Secret-Token": secret} if secret is not None else {})


def test_chat_is_off_until_telegram_is_configured(api, make_player, app, monkeypatch):
    monkeypatch.setitem(app.config, "TELEGRAM_BOT_TOKEN", "")
    make_player(api)
    assert api.get('/api/v1/chat').get_json() == {"enabled": False, "messages": [], "unread": 0}
    assert api.post('/api/v1/chat/messages', {"text": "hi"}).status_code == 501


def test_chat_requires_login(api, telegram):
    assert api.get('/api/v1/chat').status_code == 401
    assert api.post('/api/v1/chat/messages', {"text": "hi"}).status_code == 401


def test_first_message_creates_a_topic_named_after_the_player_and_posts_into_it(api, make_player, telegram):
    me = make_player(api)
    r = api.post('/api/v1/chat/messages', {"text": "Hello <b>team</b>"})
    assert r.status_code == 201 and r.get_json()["sender"] == "player"
    topic = next(p for m, p in telegram.calls if m == "createForumTopic")
    assert topic == {"chat_id": GROUP, "name": me["username"]}
    header, message = telegram.sent()
    assert me["email"] in header["text"] and header["message_thread_id"] == 101
    assert message["text"] == "💬 Hello &lt;b&gt;team&lt;/b&gt;" and message["message_thread_id"] == 101      # user text can't inject markup
    assert SupportChat.query.one().telegram_topic_id == 101


def test_later_messages_reuse_the_same_topic(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "one"})
    api.post('/api/v1/chat/messages', {"text": "two"})
    assert sum(1 for m, _ in telegram.calls if m == "createForumTopic") == 1
    assert telegram.sent()[-1]["message_thread_id"] == 101 and ChatMessage.query.count() == 2


def test_a_deleted_topic_is_replaced_and_the_message_still_goes_through(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "one"})
    telegram.fail_next.append(tg.TelegramError("Bad Request: message thread not found", 400))
    r = api.post('/api/v1/chat/messages', {"text": "two"})
    assert r.status_code == 201
    assert SupportChat.query.one().telegram_topic_id == 102 and telegram.sent()[-1]["message_thread_id"] == 102


def test_when_telegram_is_unreachable_the_message_is_not_pretended_sent(api, make_player, telegram):
    make_player(api)
    telegram.down = True
    r = api.post('/api/v1/chat/messages', {"text": "anyone there?"})
    assert r.status_code == 502 and r.get_json()["code"] == "chat_undelivered"
    assert ChatMessage.query.count() == 0


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
def test_empty_and_oversized_messages_are_refused(api, make_player, telegram, text):
    make_player(api)
    assert api.post('/api/v1/chat/messages', {"text": text}).status_code == 400
    assert telegram.calls == []


def test_an_operator_reply_in_the_players_topic_reaches_the_website(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "help"})
    assert _reply(api, 101, "Hi! How can I help?").status_code == 200
    state = api.get('/api/v1/chat').get_json()
    assert state["unread"] == 1
    assert [m["sender"] for m in state["messages"]] == ["player", "operator"]
    assert state["messages"][1]["body"] == "Hi! How can I help?" and state["messages"][1]["operator"] == "Alex"
    assert api.post('/api/v1/chat/read').get_json()["unread"] == 0
    assert api.get('/api/v1/chat').get_json()["unread"] == 0


def test_polling_with_after_returns_only_new_messages(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "help"})
    last = api.get('/api/v1/chat').get_json()["messages"][-1]["id"]
    _reply(api, 101, "one", message_id=901)
    _reply(api, 101, "two", message_id=902)
    new = api.get(f'/api/v1/chat?after={last}').get_json()["messages"]
    assert [m["body"] for m in new] == ["one", "two"]


def test_replies_go_only_to_the_right_player(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "mine"})
    api.post('/api/v1/auth/logout')
    make_player(api, "player_two", "p2@example.com")
    api.post('/api/v1/chat/messages', {"text": "theirs"})          # topic 102
    _reply(api, 102, "for player two", message_id=910)
    assert [m["body"] for m in api.get('/api/v1/chat').get_json()["messages"]] == ["theirs", "for player two"]
    api.post('/api/v1/auth/logout')
    api.post('/api/v1/auth/login', {"identifier": "p1@example.com", "password": "Sup3rSecret!x"})
    api.refresh()
    assert [m["body"] for m in api.get('/api/v1/chat').get_json()["messages"]] == ["mine"]


def test_webhook_rejects_a_wrong_or_missing_secret(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "hi"})
    assert _reply(api, 101, secret="wrong").status_code == 403
    assert _reply(api, 101, secret=None).status_code == 403
    assert ChatMessage.query.filter_by(sender="operator").count() == 0


def test_webhook_refuses_when_no_secret_is_configured(api, make_player, telegram, app, monkeypatch):
    monkeypatch.setitem(app.config, "TELEGRAM_WEBHOOK_SECRET", "")
    assert _reply(api, 101, secret="").status_code == 503


@pytest.mark.parametrize("kwargs", [
    {"chat": "-100999"},                 # another group
    {"bot": True},                       # a bot (including ourselves)
    {"text": "/close"},                  # a command
    {"thread": None},                    # the General topic
])
def test_webhook_ignores_messages_that_are_not_operator_replies(api, make_player, telegram, kwargs):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "hi"})
    thread = kwargs.pop("thread", 101)
    assert _reply(api, thread, **kwargs).status_code == 200
    assert ChatMessage.query.filter_by(sender="operator").count() == 0


def test_a_redelivered_update_is_stored_once(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "hi"})
    for _ in range(3):
        assert _reply(api, 101, "same", message_id=950).status_code == 200
    assert ChatMessage.query.filter_by(sender="operator").count() == 1


def test_an_attachment_reply_shows_a_placeholder(api, make_player, telegram):
    make_player(api)
    api.post('/api/v1/chat/messages', {"text": "hi"})
    _reply(api, 101, text="", message_id=960, photo=[{"file_id": "x"}])
    assert "attachment" in api.get('/api/v1/chat').get_json()["messages"][-1]["body"]


# ------------------------------------------------------------------ deposit alerts
def test_deposit_alert_has_the_agreed_layout():
    text = tg.deposit_text(ref="DEP-1793351861559-D90F2CCD", username="Gardoin", email="g@example.com", amount_cents=5000,
                           method="Victoria", sender="Gregory Ardoin")
    assert text.split("\n") == ["📋 Ref: DEP-1793351861559-D90F2CCD", "👤 User: Gardoin (g@example.com)", "💰 Amount: $50.00",
                                "💳 Method: Victoria", "🙍 Sender: Gregory Ardoin", "📊 Status: Approved ✅"]


def test_deposit_alert_leaves_out_the_sender_when_it_is_unknown_and_escapes_text():
    text = tg.deposit_text(ref="R", username="<b>x</b>", email="e@x.io", amount_cents=1234, method="CashApp")
    assert "Sender" not in text and "&lt;b&gt;x&lt;/b&gt;" in text and "$12.34" in text


def test_the_alert_is_sent_only_after_the_transaction_commits(app, telegram):
    fields = dict(ref="R1", username="u", email="e@x.io", amount_cents=2500, method="CashApp")
    tg.queue_deposit_alert(db.session, **fields)
    assert telegram.calls == []                      # nothing yet: still inside the transaction
    db.session.commit()
    assert [p["text"] for p in telegram.sent()][0].startswith("📋 Ref: R1")
    telegram.calls.clear()
    db.session.execute(db.text("SELECT 1"))          # a real deposit always has database work (an open transaction) first
    tg.queue_deposit_alert(db.session, **fields)
    db.session.rollback()
    db.session.commit()
    assert telegram.calls == []                      # a rolled-back deposit never produces an alert


def test_a_deposit_alert_goes_to_the_deposit_topic_when_one_is_set(app, telegram, monkeypatch):
    monkeypatch.setitem(app.config, "TELEGRAM_DEPOSIT_TOPIC_ID", "42")
    tg.queue_deposit_alert(db.session, ref="R2", username="u", email="e@x.io", amount_cents=100, method="Chime")
    db.session.commit()
    assert telegram.sent()[0]["message_thread_id"] == 42


def test_a_telegram_failure_never_breaks_the_deposit(app, telegram):
    telegram.down = True
    tg.queue_deposit_alert(db.session, ref="R3", username="u", email="e@x.io", amount_cents=100, method="Chime")
    db.session.commit()                              # must not raise


def test_no_alert_when_telegram_is_not_configured(app, telegram, monkeypatch):
    monkeypatch.setitem(app.config, "TELEGRAM_BOT_TOKEN", "")
    tg.queue_deposit_alert(db.session, ref="R4", username="u", email="e@x.io", amount_cents=100, method="Chime")
    db.session.commit()
    assert telegram.calls == []
