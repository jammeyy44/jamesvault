"""Wallet ledger, deposits, signed webhooks, cashouts and wallet-funded Add Cash."""
import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from sqlalchemy import text

from app import db
from app.models_site import (
    CashRequest, CatalogGame, PaymentMethodSetting, PaymentOrder, Player, WalletEntry, WebhookDelivery, WithdrawalOrder,
)
from app.routes.site import wallet as wallet_routes
from app.services import wallet as ledger
from app.services.payments import PaymentError
from tests.test_game_access import FakeGateway, features, game  # noqa: F401  (fixtures)

SECRET = "whsec_test_secret"
KEY = "idem-key-{:08d}".format
FP = "device-fingerprint-0001"


# ------------------------------------------------------------------ fakes / helpers
class FakePayments:
    name = "live"

    def __init__(self):
        self.deposits, self.withdrawals = [], []
        self.deposit_status, self.deposit_paid = "paid", None
        self.withdrawal_error = None

    def methods(self):
        return {"deposits": [{"id": "m-cash", "value": "cashapp", "name": "CashApp"},
                             {"id": "m-chime", "value": "chime", "name": "Chime"},
                             {"id": "m-card", "value": "card", "name": "Card Payments"}],
                "withdrawals": [{"id": "w-cash", "value": "cashapp", "name": "CashApp"},
                                {"id": "w-card", "value": "card", "name": "Card Payments"}]}

    def create_deposit(self, **kw):
        self.deposits.append(kw)
        n = len(self.deposits)
        return {"id": f"dep{n:021d}", "referenceId": f"REF-{n}", "status": "pending",
                "paymentUrl": f"https://pay.example.com/checkout/{n}", "isChimney": False}

    def get_deposit(self, deposit_id):
        d = {"id": deposit_id, "status": self.deposit_status}
        if self.deposit_paid is not None:
            d["paidAmount"] = self.deposit_paid
        else:
            idx = int(deposit_id[3:]) - 1  # ids are "dep" + zero-padded creation order
            d["amount"] = float(self.deposits[idx]["amount"]) if 0 <= idx < len(self.deposits) else 0
        return d

    def create_withdrawal(self, **kw):
        if self.withdrawal_error:
            raise self.withdrawal_error
        self.withdrawals.append(kw)
        return {"id": f"wd{len(self.withdrawals):021d}", "referenceId": f"W-{len(self.withdrawals)}", "status": "pending"}


@pytest.fixture()
def pay(app, monkeypatch, features):
    """Live-mode wallet with a fake payment provider."""
    fake = FakePayments()
    features(wallet=True)
    cfg = app.config
    old = (cfg["PAYDORA_API_KEY"], cfg["PAYDORA_WEBHOOK_SECRET"])
    cfg["PAYDORA_API_KEY"], cfg["PAYDORA_WEBHOOK_SECRET"] = "pk_test", SECRET
    wallet_routes._methods_cache.update(at=0.0, data=None, mode=None)
    monkeypatch.setattr("app.routes.site.wallet.get_payments", lambda: fake)
    monkeypatch.setattr("app.routes.webhooks.get_payments", lambda: fake)
    monkeypatch.setattr("app.routes.site.admin_wallet.get_payments", lambda: fake)
    monkeypatch.setattr("app.services.withdrawals.get_payments", lambda: fake)
    yield fake
    cfg["PAYDORA_API_KEY"], cfg["PAYDORA_WEBHOOK_SECRET"] = old
    wallet_routes._methods_cache.update(at=0.0, data=None, mode=None)


@pytest.fixture()
def sandbox_wallet(app, features):
    features(wallet=True, sandbox=True)
    wallet_routes._methods_cache.update(at=0.0, data=None, mode=None)
    yield
    wallet_routes._methods_cache.update(at=0.0, data=None, mode=None)


def hook(app, event, data, delivery="d-0001", secret=SECRET, sign=True):
    raw = json.dumps({"event": event, "data": data, "deliveryId": delivery}).encode()
    headers = {"Content-Type": "application/json"}
    if sign:
        headers["X-Signature"] = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return app.test_client().post('/api/v1/webhooks/paydora', data=raw, headers=headers)


def balance(player_id):
    return db.session.get(Player, player_id).wallet_cents


def deposit(api, amount=20, method="m-chime", n=1):
    return api.post('/api/v1/wallet/deposits', {"method_id": method, "amount": amount, "idempotency_key": KEY(n),
                                                "device_fingerprint": FP})


def fund(player_id, cents, ref="seed"):
    ledger.credit(player_id, cents, 'adjustment', 'test', f"{ref}-{player_id}-{cents}")
    db.session.commit()


# ------------------------------------------------------------------ ledger
def test_ledger_credit_is_idempotent_and_debit_is_compare_and_set(app, api, make_player):
    p = make_player(api)
    assert ledger.credit(p["id"], 1000, 'deposit', 'o', 1) is True
    assert ledger.credit(p["id"], 1000, 'deposit', 'o', 1) is False  # replay changes nothing
    db.session.commit()
    assert balance(p["id"]) == 1000
    assert ledger.debit(p["id"], 700, 'withdrawal', 'o', 1) is True
    db.session.commit()
    with pytest.raises(ledger.InsufficientFunds):
        ledger.debit(p["id"], 400, 'withdrawal', 'o', 2)  # only 300 left: cannot overspend
    db.session.rollback()
    assert balance(p["id"]) == 300
    assert WalletEntry.query.filter_by(player_id=p["id"]).count() == 2


def test_wallet_is_unavailable_when_disabled(api, make_player):
    make_player(api)
    body = api.get('/api/v1/wallet').get_json()
    assert body["enabled"] is False and body["balance"] is None and body["deposit_methods"] == []
    assert deposit(api).status_code == 501


# ------------------------------------------------------------------ sandbox
def test_sandbox_deposit_credits_once_and_replays_are_safe(api, make_player, sandbox_wallet):
    p = make_player(api)
    w = api.get('/api/v1/wallet').get_json()
    assert w["mode"] == "sandbox" and w["sandbox_notice"] and w["balance"] == "0.00"
    assert {m["value"] for m in w["deposit_methods"]} >= {"cashapp", "chime"}
    r = deposit(api, 25, "sbx-d-chime")
    assert r.status_code == 201 and r.get_json()["status"] == "paid" and r.get_json()["sandbox"] is True
    again = deposit(api, 25, "sbx-d-chime")
    assert again.get_json()["id"] == r.get_json()["id"]
    assert balance(p["id"]) == 2500 and PaymentOrder.query.count() == 1
    assert api.get('/api/v1/wallet').get_json()["balance"] == "25.00"


def test_sandbox_cashout_completes_after_staff_approval(api, make_player, sandbox_wallet, staff_client):
    p = make_player(api)
    fund(p["id"], 5000)
    r = api.post('/api/v1/wallet/withdrawals', {"method_id": "sbx-w-cashapp", "amount": 50, "address": "$player",
                                                "idempotency_key": KEY(1)})
    assert r.status_code == 201 and balance(p["id"]) == 0  # held immediately
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/withdrawals/{r.get_json()["id"]}', {"action": "approve"}).get_json()["status"] == "completed"


# ------------------------------------------------------------------ deposit validation
def test_deposit_input_validation(api, make_player, pay):
    make_player(api)
    assert api.post('/api/v1/wallet/deposits', {"method_id": "m-chime", "amount": 20, "idempotency_key": KEY(1)}).status_code == 400  # no fingerprint
    assert api.post('/api/v1/wallet/deposits', {"method_id": "m-chime", "amount": 20, "idempotency_key": "x",
                                                "device_fingerprint": FP}).status_code == 400
    assert deposit(api, 20, "nope").status_code == 400
    for bad in (0, -5, "abc", 10.005, "NaN"):
        assert deposit(api, bad, "m-chime", 2).status_code == 400
    r = deposit(api, 23.5, "m-cash", 3)  # CashApp only accepts listed amounts
    assert r.status_code == 400 and "9.99" in r.get_json()["error"]
    assert PaymentOrder.query.count() == 0 and pay.deposits == []


def test_methods_come_from_provider_and_badges_only_from_admin_settings(api, make_player, pay, admin_api):
    make_player(api)
    names = [m["name"] for m in api.get('/api/v1/wallet').get_json()["deposit_methods"]]
    assert set(names) == {"CashApp", "Chime", "Card Payments"}
    assert all(m["badge"] is None for m in api.get('/api/v1/wallet').get_json()["deposit_methods"])  # nothing invented
    admin_api.post('/api/v1/admin/payment-methods', {"value": "chime", "badge": "No fee", "badge_tone": "green", "sort_order": -1})
    admin_api.post('/api/v1/admin/payment-methods', {"value": "card", "is_enabled": False})
    got = api.get('/api/v1/wallet').get_json()["deposit_methods"]
    assert got[0]["value"] == "chime" and got[0]["badge"] == "No fee"
    assert "card" not in {m["value"] for m in got}
    # card payouts are never offered (we do not handle card numbers)
    assert all(m["value"] != "card" for m in api.get('/api/v1/wallet').get_json()["withdrawal_methods"])


# ------------------------------------------------------------------ live deposit + webhooks
def test_live_deposit_creates_pending_order_and_does_not_credit(api, make_player, pay):
    p = make_player(api)
    r = deposit(api, 25, "m-chime")
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "pending" and body["payment_url"].startswith("https://pay.example.com/")
    assert balance(p["id"]) == 0
    sent = pay.deposits[0]
    assert sent["customer_ip"] and sent["device_fingerprint"] == FP and sent["user_name"] == p["username"]
    assert sent["idempotency_key"].startswith("jv-dep-")


def test_webhook_signature_is_required(app, api, make_player, pay):
    make_player(api)
    data = {"depositId": "x"}
    assert hook(app, "deposit.paid", data, sign=False).status_code == 401
    assert hook(app, "deposit.paid", data, secret="whsec_wrong").status_code == 401
    app.config["PAYDORA_WEBHOOK_SECRET"] = ""
    assert hook(app, "deposit.paid", data).status_code == 503  # unconfigured: refuse everything
    app.config["PAYDORA_WEBHOOK_SECRET"] = SECRET


def test_paid_webhook_credits_once_even_if_delivered_repeatedly(app, api, make_player, pay):
    p = make_player(api)
    dep_id = deposit(api, 25, "m-chime").get_json()
    order = PaymentOrder.query.one()
    payload = {"depositId": order.provider_deposit_id, "status": "paid", "amount": 25.0, "paidAmount": 25.0}
    assert hook(app, "deposit.paid", payload, delivery="d-1").status_code == 200
    assert balance(p["id"]) == 2500 and db.session.get(PaymentOrder, order.id).status == "paid"
    assert hook(app, "deposit.paid", payload, delivery="d-1").get_json().get("duplicate") is True  # retry
    assert hook(app, "deposit.paid", payload, delivery="d-2").status_code == 200  # different delivery, same deposit
    assert balance(p["id"]) == 2500
    assert WalletEntry.query.filter_by(kind="deposit").count() == 1


def test_webhook_claim_is_checked_against_the_provider_before_crediting(app, api, make_player, pay):
    p = make_player(api)
    deposit(api, 25, "m-chime")
    order = PaymentOrder.query.one()
    pay.deposit_status = "pending"  # a (validly signed) paid event the provider does not confirm
    hook(app, "deposit.paid", {"depositId": order.provider_deposit_id, "amount": 25.0}, delivery="d-9")
    assert balance(p["id"]) == 0
    assert WebhookDelivery.query.filter_by(handled=False).count() == 1


def test_credit_uses_the_amount_that_actually_arrived(app, api, make_player, pay):
    p = make_player(api)
    deposit(api, 25, "m-chime")
    order = PaymentOrder.query.one()
    pay.deposit_paid = 24.5
    hook(app, "deposit.paid", {"depositId": order.provider_deposit_id}, delivery="d-3")
    assert balance(p["id"]) == 2450


def test_failed_and_refunded_events(app, api, make_player, pay):
    p = make_player(api)
    deposit(api, 25, "m-chime", 1)
    deposit(api, 20, "m-chime", 2)
    o1, o2 = PaymentOrder.query.order_by(PaymentOrder.id).all()
    hook(app, "deposit.failed", {"depositId": o1.provider_deposit_id}, delivery="f-1")
    assert db.session.get(PaymentOrder, o1.id).status == "failed" and balance(p["id"]) == 0
    hook(app, "deposit.paid", {"depositId": o2.provider_deposit_id, "paidAmount": 20.0}, delivery="p-1")
    assert balance(p["id"]) == 2000
    hook(app, "deposit.refunded", {"depositId": o2.provider_deposit_id, "refundAmount": 20.0}, delivery="r-1")
    hook(app, "deposit.refunded", {"depositId": o2.provider_deposit_id, "refundAmount": 20.0}, delivery="r-2")
    assert balance(p["id"]) == 0 and db.session.get(PaymentOrder, o2.id).status == "refunded"


def test_unmatched_payment_is_never_auto_credited_and_staff_can_credit_it_once(app, api, make_player, pay, admin_api):
    p = make_player(api)
    r = hook(app, "deposit.paid", {"depositId": "chime0000000000000000001", "amount": 40.0, "paidAmount": 40.0,
                                   "isChimney": True, "memo": p["username"], "payerName": "Jordan M"}, delivery="c-1")
    assert r.status_code == 200 and balance(p["id"]) == 0  # memo text is a hint, not proof
    item = admin_api.get('/api/v1/admin/unmatched-payments').get_json()["items"][0]
    assert item["amount"] == "40.00" and item["memo"] == p["username"]
    assert admin_api.patch(f'/api/v1/admin/unmatched-payments/{item["id"]}', {"action": "credit", "username": "nobody"}).status_code == 400
    assert admin_api.patch(f'/api/v1/admin/unmatched-payments/{item["id"]}', {"action": "credit", "username": p["username"]}).status_code == 200
    assert balance(p["id"]) == 4000
    assert admin_api.patch(f'/api/v1/admin/unmatched-payments/{item["id"]}', {"action": "credit", "username": p["username"]}).status_code == 400
    assert balance(p["id"]) == 4000


# ------------------------------------------------------------------ cashouts
def _withdraw(api, amount=50, n=1, address="$player", method="w-cash"):
    return api.post('/api/v1/wallet/withdrawals', {"method_id": method, "amount": amount, "address": address,
                                                   "idempotency_key": KEY(n)})


def test_cashout_holds_funds_and_validates(api, make_player, pay):
    p = make_player(api)
    assert _withdraw(api).status_code == 402  # nothing in the wallet
    fund(p["id"], 10000)
    assert _withdraw(api, 5, 2).status_code == 400       # below minimum
    assert _withdraw(api, 49.99, 7).status_code == 400   # one cent below the $50 minimum
    assert _withdraw(api, 9999, 3).status_code == 400    # above maximum
    assert _withdraw(api, 50, 4, address="").status_code == 400
    assert _withdraw(api, 50, 5, method="w-card").status_code == 400  # card payouts unsupported
    r = _withdraw(api, 50, 6)
    assert r.status_code == 201 and balance(p["id"]) == 5000
    assert _withdraw(api, 50, 6).get_json()["id"] == r.get_json()["id"] and balance(p["id"]) == 5000  # replay
    assert "$player" not in r.get_data(as_text=True)  # destination is never echoed to the player
    assert db.session.execute(text("SELECT address_enc FROM withdrawal_orders")).scalar().startswith("enc:")


def test_player_can_cancel_pending_cashout_once(api, make_player, pay):
    p = make_player(api)
    fund(p["id"], 10000)
    wid = _withdraw(api).get_json()["id"]
    assert api.post(f'/api/v1/wallet/withdrawals/{wid}/cancel').status_code == 200 and balance(p["id"]) == 10000
    assert api.post(f'/api/v1/wallet/withdrawals/{wid}/cancel').status_code == 409 and balance(p["id"]) == 10000


def test_cannot_cancel_someone_elses_cashout(app, api, make_player, pay):
    from tests.conftest import Api
    p = make_player(api)
    fund(p["id"], 10000)
    wid = _withdraw(api).get_json()["id"]
    other = Api(app.test_client())
    make_player(other, username="someone_else", email="s@example.com")
    assert other.post(f'/api/v1/wallet/withdrawals/{wid}/cancel').status_code == 409
    assert db.session.get(WithdrawalOrder, wid).status == "pending_review"


def test_approve_sends_exactly_once_and_only_superadmin_can(api, make_player, pay, staff_client):
    p = make_player(api)
    fund(p["id"], 10000)
    wid = _withdraw(api).get_json()["id"]
    helper = staff_client("helper", "support")
    assert helper.patch(f'/api/v1/admin/withdrawals/{wid}', {"action": "approve"}).status_code == 403
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/withdrawals/{wid}', {"action": "approve"}).get_json()["status"] == "submitted"
    assert root.patch(f'/api/v1/admin/withdrawals/{wid}', {"action": "approve"}).status_code == 409
    assert len(pay.withdrawals) == 1 and pay.withdrawals[0]["address"] == "$player"
    assert pay.withdrawals[0]["idempotency_key"] == f"jv-wd-{wid}"


def test_provider_refusal_returns_the_money_but_unknown_outcome_holds_it(api, make_player, pay, staff_client):
    p = make_player(api)
    fund(p["id"], 10000)
    root = staff_client("root", "superadmin")
    w1 = _withdraw(api, 50, 1).get_json()["id"]
    pay.withdrawal_error = PaymentError("Amount exceeds the per-withdrawal cap", definitive=True)
    assert root.patch(f'/api/v1/admin/withdrawals/{w1}', {"action": "approve"}).get_json()["status"] == "failed"
    assert balance(p["id"]) == 10000  # refunded

    w2 = _withdraw(api, 50, 2).get_json()["id"]
    pay.withdrawal_error = PaymentError("timeout", definitive=False)
    assert root.patch(f'/api/v1/admin/withdrawals/{w2}', {"action": "approve"}).get_json()["status"] == "needs_review"
    assert balance(p["id"]) == 5000  # still held: the payout may have gone out
    assert root.patch(f'/api/v1/admin/withdrawals/{w2}', {"action": "approve"}).status_code == 409
    assert root.patch(f'/api/v1/admin/withdrawals/{w2}', {"action": "resolve_failed"}).status_code == 200
    assert balance(p["id"]) == 10000
    assert root.patch(f'/api/v1/admin/withdrawals/{w2}', {"action": "resolve_failed"}).status_code == 409
    assert balance(p["id"]) == 10000


def test_reject_refunds_once(api, make_player, pay, staff_client):
    p = make_player(api)
    fund(p["id"], 10000)
    wid = _withdraw(api).get_json()["id"]
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/withdrawals/{wid}', {"action": "reject"}).status_code == 200
    assert root.patch(f'/api/v1/admin/withdrawals/{wid}', {"action": "reject"}).status_code == 409
    assert balance(p["id"]) == 10000 and pay.withdrawals == []


def test_withdrawal_webhooks(app, api, make_player, pay, staff_client):
    p = make_player(api)
    fund(p["id"], 20000)
    root = staff_client("root", "superadmin")
    done, cancelled, lost = (_withdraw(api, 50, n).get_json()["id"] for n in (1, 2, 3))
    for wid in (done, cancelled, lost):
        root.patch(f'/api/v1/admin/withdrawals/{wid}', {"action": "approve"})
    pid = {wid: db.session.get(WithdrawalOrder, wid).provider_withdrawal_id for wid in (done, cancelled, lost)}
    assert balance(p["id"]) == 5000

    hook(app, "withdrawal.completed", {"withdrawalId": pid[done]}, delivery="w-1")
    assert db.session.get(WithdrawalOrder, done).status == "completed"

    hook(app, "withdrawal.cancelled", {"withdrawalId": pid[cancelled]}, delivery="w-2")
    hook(app, "withdrawal.cancelled", {"withdrawalId": pid[cancelled]}, delivery="w-3")
    assert db.session.get(WithdrawalOrder, cancelled).status == "cancelled" and balance(p["id"]) == 10000  # refunded once

    hook(app, "withdrawal.failed_at_provider", {"withdrawalId": pid[lost]}, delivery="w-4")
    assert db.session.get(WithdrawalOrder, lost).status == "failed_at_provider" and balance(p["id"]) == 10000  # staff decide
    assert root.patch(f'/api/v1/admin/withdrawals/{lost}', {"action": "credit_back"}).status_code == 200
    assert root.patch(f'/api/v1/admin/withdrawals/{lost}', {"action": "credit_back"}).status_code == 409
    assert balance(p["id"]) == 15000


# ------------------------------------------------------------------ history
def test_history_lists_orders_and_ledger_for_the_owner_only(app, api, make_player, pay):
    from tests.conftest import Api
    p = make_player(api)
    deposit(api, 25, "m-chime")
    fund(p["id"], 5000)
    h = api.get('/api/v1/wallet/history').get_json()
    assert h["orders"][0]["type"] == "deposit" and h["ledger"][0]["amount"] == "50.00"
    other = Api(app.test_client())
    make_player(other, username="someone_else", email="s@example.com")
    h2 = other.get('/api/v1/wallet/history').get_json()
    assert h2["orders"] == [] and h2["ledger"] == []


# ------------------------------------------------------------------ Add Cash from the wallet
def test_add_cash_spends_wallet_funds_and_recharges(api, make_player, game, sandbox_wallet, features):
    p = make_player(api)
    api.post('/api/v1/games/game-vault/access')
    state = api.get('/api/v1/games/game-vault/access').get_json()
    assert state["wallet_funded"] is True and state["wallet_balance"] == "0.00"
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": KEY(1)})
    assert r.status_code == 402 and r.get_json()["code"] == "insufficient_funds"  # no funds, no free credit
    assert CashRequest.query.count() == 0

    fund(p["id"], 2500)
    ok = api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": KEY(2)})
    assert ok.status_code == 201 and ok.get_json()["status"] == "completed"
    assert balance(p["id"]) == 1500
    assert api.get('/api/v1/games/game-vault/balance').get_json()["balance"] == "10.00"
    again = api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": KEY(2)})
    assert again.get_json()["id"] == ok.get_json()["id"] and balance(p["id"]) == 1500  # replay never double-spends


class RefusingGateway(FakeGateway):
    def recharge(self, account, amount):
        from app.services.gateway import GatewayError
        raise GatewayError("The game provider could not complete that request. Please try again later.")


class UnknownGateway(FakeGateway):
    def recharge(self, account, amount):
        raise TimeoutError("read timed out")


def _live_wallet_cash(monkeypatch, features, gw):
    features(wallet=True, game_accounts=True)
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: gw)
    monkeypatch.setattr("app.services.gateway.get_gateway", lambda: gw)


def test_failed_recharge_refunds_the_wallet(api, make_player, game, features, monkeypatch):
    p = make_player(api)
    gw = RefusingGateway()
    _live_wallet_cash(monkeypatch, features, gw)
    api.post('/api/v1/games/game-vault/access')
    fund(p["id"], 2500)
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": KEY(1)})
    assert r.get_json()["status"] == "failed" and balance(p["id"]) == 2500


def test_unknown_recharge_outcome_holds_funds_until_staff_resolve(api, make_player, game, features, monkeypatch, staff_client):
    p = make_player(api)
    _live_wallet_cash(monkeypatch, features, UnknownGateway())
    api.post('/api/v1/games/game-vault/access')
    fund(p["id"], 2500)
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": KEY(1)})
    assert r.get_json()["status"] == "needs_review" and balance(p["id"]) == 1500
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/cash-requests/{r.get_json()["id"]}', {"action": "resolve_failed"}).status_code == 200
    assert balance(p["id"]) == 2500
    assert root.patch(f'/api/v1/admin/cash-requests/{r.get_json()["id"]}', {"action": "resolve_failed"}).status_code == 409
    assert balance(p["id"]) == 2500


def test_free_amount_methods_enforce_server_side_bounds(api, make_player, sandbox_wallet):
    p = make_player(api)
    w = api.get('/api/v1/wallet').get_json()
    assert w["deposit"] == {"min": "5", "max": "1000"}
    paypal = next(m for m in w["deposit_methods"] if m["value"] == "paypal")
    assert paypal["amounts"] is None  # no fixed list: the popup offers the full amount editor
    for bad, n in ((0.5, 1), (4.99, 6), (1001, 2), (10.005, 3)):
        assert deposit(api, bad, paypal["id"], n).status_code == 400
    assert balance(p["id"]) == 0 and PaymentOrder.query.count() == 0
    assert deposit(api, 20, paypal["id"], 4).status_code == 201 and balance(p["id"]) == 2000
    assert deposit(api, 1000, paypal["id"], 5).status_code == 201


def test_fixed_amount_methods_still_reject_arbitrary_amounts(api, make_player, sandbox_wallet):
    make_player(api)
    chime = next(m for m in api.get('/api/v1/wallet').get_json()["deposit_methods"] if m["value"] == "chime")
    assert chime["amounts"] and deposit(api, 23, chime["id"], 1).status_code == 400  # $23 is not in Chime's list


# ------------------------------------------------------------------ minimum withdrawal: $50
def test_minimum_withdrawal_is_fifty_and_exactly_fifty_in_the_wallet_can_withdraw(api, make_player, pay):
    p = make_player(api)
    assert api.get('/api/v1/wallet').get_json()["cashout"]["min"] == "50"
    fund(p["id"], 5000)                                                    # exactly $50
    r = _withdraw(api, 50, 1)
    assert r.status_code == 201 and balance(p["id"]) == 0                  # the whole $50 can be withdrawn


def test_below_the_minimum_is_refused_with_a_clear_message_even_with_a_big_balance(api, make_player, pay):
    p = make_player(api)
    fund(p["id"], 100000)
    for n, amount in enumerate((49.99, 49, 20, 1, 0.01), start=1):
        r = _withdraw(api, amount, n)
        assert r.status_code == 400 and r.get_json()["code"] == "below_minimum" and "$50" in r.get_json()["error"], amount
    assert balance(p["id"]) == 100000 and WithdrawalOrder.query.count() == 0


def test_a_wallet_under_fifty_cannot_withdraw_at_all(api, make_player, pay):
    p = make_player(api)
    fund(p["id"], 4999)                                                    # $49.99
    assert _withdraw(api, 50, 1).status_code == 402                        # the minimum amount exceeds the balance
    assert _withdraw(api, 49.99, 2).status_code == 400                     # and anything smaller is under the minimum
    assert balance(p["id"]) == 4999 and WithdrawalOrder.query.count() == 0
