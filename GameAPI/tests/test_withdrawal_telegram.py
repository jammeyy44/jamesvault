"""Cashout requests in Telegram: the alert, the Approve / Reject buttons, who may press them, and the payout request to Paydora."""
import pytest

from app import db
from app.models_site import Player, WithdrawalOrder
from app.services import telegram as tg
from tests.test_telegram import FakeTelegram, GROUP, SECRET, telegram  # noqa: F401  (helpers + fixture)
from tests.test_wallet import FP, KEY, balance, features, fund, hook, pay  # noqa: F401


@pytest.fixture(autouse=True)
def _more_telegram_methods(monkeypatch):
    """The shared fake only knows chat calls: teach it the ones cashout buttons use."""
    orig = FakeTelegram.__call__
    state = {"members": {7: "administrator"}}   # user 7 (the default presser) is a group admin; others are plain members

    def call(self, token, method, payload, files=None):
        if method in ("editMessageText", "editMessageReplyMarkup", "answerCallbackQuery"):
            self.calls.append((method, dict(payload)))
            return True
        if method == "getChatMember":
            self.calls.append((method, dict(payload)))
            return {"status": state["members"].get(payload["user_id"], "member")}
        return orig(self, token, method, payload, files)
    monkeypatch.setattr(FakeTelegram, "__call__", call)
    monkeypatch.setattr(FakeTelegram, "members", state["members"], raising=False)
    return state


def _request_cashout(api, make_player, amount=60, n=1):
    p = make_player(api)
    fund(p["id"], 20000)
    r = api.post('/api/v1/wallet/withdrawals', {"method_id": "w-cash", "amount": amount, "address": "$gregory", "idempotency_key": KEY(n)})
    assert r.status_code == 201, r.get_json()
    return p, r.get_json()["id"]


def _press(api, data, user_id=7, first="Boss", message_id=None, chat=GROUP, is_bot=False):
    order = WithdrawalOrder.query.order_by(WithdrawalOrder.id.desc()).first()
    cb = {"id": "cb1", "from": {"id": user_id, "is_bot": is_bot, "first_name": first}, "data": data,
          "message": {"message_id": message_id or order.telegram_message_id, "chat": {"id": int(chat)}}}
    return api.c.post('/api/v1/webhooks/telegram', json={"update_id": 1, "callback_query": cb}, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET})


def _answers(telegram):
    return [p for m, p in telegram.calls if m == "answerCallbackQuery"]


def test_a_new_cashout_request_is_posted_with_approve_and_reject_buttons(api, make_player, pay, telegram):
    p, wid = _request_cashout(api, make_player)
    (msg,) = [x for x in telegram.sent() if "WD-" in x["text"]]
    assert msg["text"].splitlines()[:3] == [f"📋 Ref: WD-{wid}", f"👤 User: {p['username']} ({p['email']})", "💰 Amount: $60.00"]
    assert "💳 Method: CashApp" in msg["text"] and "📍 Send to: $gregory" in msg["text"] and "Pending review" in msg["text"]
    buttons = [b["callback_data"] for row in msg["reply_markup"]["inline_keyboard"] for b in row]
    assert buttons == [f"wd:ask:{wid}", f"wd:reject:{wid}"]
    assert WithdrawalOrder.query.one().telegram_message_id is not None


def test_nothing_is_posted_when_telegram_is_not_configured(api, make_player, pay, telegram, app, monkeypatch):
    monkeypatch.setitem(app.config, "TELEGRAM_BOT_TOKEN", "")
    _request_cashout(api, make_player)
    assert telegram.calls == []


def test_approve_asks_for_confirmation_then_sends_the_payout_to_paydora_once(api, make_player, pay, telegram):
    p, wid = _request_cashout(api, make_player)
    assert _press(api, f"wd:ask:{wid}").status_code == 200
    assert pay.withdrawals == []                                                       # one tap alone moves no money
    edit = [x for m, x in telegram.calls if m == "editMessageReplyMarkup"][-1]
    assert [b["callback_data"] for r in edit["reply_markup"]["inline_keyboard"] for b in r] == [f"wd:yes:{wid}", f"wd:back:{wid}"]
    assert "$60.00" in edit["reply_markup"]["inline_keyboard"][0][0]["text"]

    _press(api, f"wd:yes:{wid}")
    assert len(pay.withdrawals) == 1                                                   # the request to Paydora
    sent = pay.withdrawals[0]
    assert sent["amount"] == "60.00" and sent["address"] == "$gregory" and sent["idempotency_key"] == f"jv-wd-{wid}"
    assert WithdrawalOrder.query.one().status == "submitted"
    assert "Payout sent to Paydora" in _answers(telegram)[-1]["text"]
    final = [x for m, x in telegram.calls if m == "editMessageText"][-1]
    assert "Approved ✅" in final["text"] and "By: Boss" in final["text"] and final["reply_markup"] == {"inline_keyboard": []}

    _press(api, f"wd:yes:{wid}")                                                       # a second tap, or the website at the same time
    assert len(pay.withdrawals) == 1 and "already handled" in _answers(telegram)[-1]["text"]


def test_reject_returns_the_money_and_closes_the_message(api, make_player, pay, telegram):
    p, wid = _request_cashout(api, make_player)
    assert balance(p["id"]) == 20000 - 6000
    _press(api, f"wd:reject:{wid}")
    assert WithdrawalOrder.query.one().status == "rejected" and balance(p["id"]) == 20000 and pay.withdrawals == []
    final = [x for m, x in telegram.calls if m == "editMessageText"][-1]
    assert "Rejected ❌" in final["text"] and final["reply_markup"] == {"inline_keyboard": []}
    _press(api, f"wd:reject:{wid}")
    assert balance(p["id"]) == 20000                                                    # refunded once only


def test_back_restores_the_buttons_without_doing_anything(api, make_player, pay, telegram):
    p, wid = _request_cashout(api, make_player)
    _press(api, f"wd:ask:{wid}")
    _press(api, f"wd:back:{wid}")
    last = [x for m, x in telegram.calls if m == "editMessageReplyMarkup"][-1]
    assert [b["callback_data"] for r in last["reply_markup"]["inline_keyboard"] for b in r] == [f"wd:ask:{wid}", f"wd:reject:{wid}"]
    assert WithdrawalOrder.query.one().status == "pending_review"


def test_ordinary_group_members_cannot_press_the_buttons(api, make_player, pay, telegram, _more_telegram_methods):
    p, wid = _request_cashout(api, make_player)
    _more_telegram_methods["members"][99] = "member"
    _press(api, f"wd:yes:{wid}", user_id=99)
    _press(api, f"wd:reject:{wid}", user_id=99)
    assert WithdrawalOrder.query.one().status == "pending_review" and pay.withdrawals == [] and balance(p["id"]) == 14000
    assert all("Only the people allowed" in a["text"] for a in _answers(telegram))


def test_only_the_listed_ids_may_approve_when_a_list_is_configured(api, make_player, pay, telegram, app, monkeypatch, _more_telegram_methods):
    monkeypatch.setitem(app.config, "TELEGRAM_APPROVER_IDS", "555, 777")
    _more_telegram_methods["members"][7] = "administrator"                              # an admin, but not on the list
    p, wid = _request_cashout(api, make_player)
    _press(api, f"wd:yes:{wid}", user_id=7)
    assert pay.withdrawals == []
    _press(api, f"wd:yes:{wid}", user_id=777)
    assert len(pay.withdrawals) == 1


def test_a_group_admin_may_press_when_no_list_is_configured(api, make_player, pay, telegram, _more_telegram_methods):
    _more_telegram_methods["members"][7] = "administrator"
    p, wid = _request_cashout(api, make_player)
    _press(api, f"wd:yes:{wid}", user_id=7)
    assert len(pay.withdrawals) == 1


def test_buttons_from_other_chats_bots_or_with_bad_data_do_nothing(api, make_player, pay, telegram, _more_telegram_methods):
    _more_telegram_methods["members"][7] = "administrator"
    p, wid = _request_cashout(api, make_player)
    _press(api, f"wd:yes:{wid}", chat="-100999")
    _press(api, f"wd:yes:{wid}", is_bot=True)
    _press(api, "wd:yes:abc")
    _press(api, "evil:yes:1")
    _press(api, f"wd:nope:{wid}")
    assert pay.withdrawals == [] and WithdrawalOrder.query.one().status == "pending_review"


def test_approving_on_the_website_updates_the_telegram_message(api, make_player, pay, telegram, staff_client):
    p, wid = _request_cashout(api, make_player)
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/withdrawals/{wid}', {"action": "approve"}).get_json()["status"] == "submitted"
    final = [x for m, x in telegram.calls if m == "editMessageText"][-1]
    assert "Approved ✅" in final["text"] and final["reply_markup"] == {"inline_keyboard": []}
    assert len(pay.withdrawals) == 1


def test_the_player_cancelling_updates_the_message(api, make_player, pay, telegram):
    p, wid = _request_cashout(api, make_player)
    assert api.post(f'/api/v1/wallet/withdrawals/{wid}/cancel').status_code == 200
    final = [x for m, x in telegram.calls if m == "editMessageText"][-1]
    assert "Cancelled by the player" in final["text"]


def test_paydora_refusing_the_payout_returns_the_money(api, make_player, pay, telegram, _more_telegram_methods):
    from app.services.payments import PaymentError
    _more_telegram_methods["members"][7] = "administrator"
    pay.withdrawal_error = PaymentError("Insufficient merchant balance", definitive=True)
    p, wid = _request_cashout(api, make_player)
    _press(api, f"wd:yes:{wid}", user_id=7)
    assert WithdrawalOrder.query.one().status == "failed" and balance(p["id"]) == 20000
    assert "refused" in _answers(telegram)[-1]["text"]


def test_the_light_balance_endpoint_returns_both_balances_without_a_provider_call(api, make_player, pay):
    p = make_player(api)
    fund(p["id"], 12345)
    db.session.get(Player, p["id"]).bonus_cents = 250
    db.session.commit()
    body = api.get('/api/v1/wallet/balance').get_json()
    assert body == {"enabled": True, "balance": "123.45", "bonus_balance": "2.50"}
    assert pay.deposits == [] and pay.withdrawals == []
