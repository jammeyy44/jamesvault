"""Instant rewards, bonus balance, Deposit Boost and spending bonus on games."""
from datetime import timedelta

import pytest

from app import db
from app.models_site import (
    BonusBox, DepositBoost, PaymentOrder, Player, PlayerReward, WalletEntry,
)
from app.services import bonus, wallet as ledger
from app.utils.auth import utcnow
from tests.test_bonus import _box, diamonds, give, get, open_box, zone  # noqa: F401  (helpers + fixture)
from tests.test_game_access import FakeGateway, features, game  # noqa: F401  (fixtures)
from tests.test_wallet import (  # noqa: F401
    FakePayments, KEY, balance, deposit, fund, hook, pay, sandbox_wallet,
)


def bonus_bal(pid):
    return db.session.get(Player, pid).bonus_cents


def _boost(pid, percent=20, hours=24):
    db.session.add(DepositBoost(player_id=pid, percent=percent, expires_at=utcnow() + timedelta(hours=hours)))
    db.session.commit()


# ------------------------------------------------------------------ boxes apply instantly
@pytest.mark.parametrize("label,cents", [("$2 Free Play", 200), ("$3 Free Play", 300), ("$4 Free Play", 400), ("$5 Bonus", 500)])
def test_free_play_and_bonus_boxes_credit_the_bonus_balance_immediately(api, make_player, zone, label, cents):
    p = make_player(api)
    give(p["id"], 100)
    r = open_box(api, _box(label).id).get_json()
    assert r["reward"]["status"] == "applied" and "bonus balance" in r["note"]
    assert bonus_bal(p["id"]) == cents and balance(p["id"]) == 0          # bonus, never the withdrawable wallet
    assert r["bonus_balance"] == f"{cents / 100:.2f}"
    entry = WalletEntry.query.filter_by(kind="box_reward").one()
    assert (entry.bucket, entry.amount_cents) == ("bonus", cents)


def test_repeat_open_with_same_key_never_credits_twice(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 50)
    box = _box("$2 Free Play")
    open_box(api, box.id, 1)
    again = open_box(api, box.id, 1)
    assert again.status_code == 200 and again.get_json()["replay"] is True and again.get_json()["bonus_balance"] == "2.00"
    assert bonus_bal(p["id"]) == 200 and WalletEntry.query.filter_by(kind="box_reward").count() == 1


def test_twenty_percent_box_starts_a_timed_deposit_boost(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 50)
    r = open_box(api, _box("20% Deposit Bonus").id).get_json()
    assert r["boost"]["percent"] == 20 and 86000 < r["boost"]["seconds_left"] <= 24 * 3600
    assert "Deposit Boost" in r["note"] and bonus_bal(p["id"]) == 0  # no cash up front: it pays on deposits
    z = get(api)
    assert z["boost"]["percent"] == 20 and z["bonus_balance"] == "0.00"
    assert db.session.get(PlayerReward, r["reward"]["id"]).status == "applied"


def test_a_second_boost_extends_and_never_weakens_a_running_one(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 100)
    _boost(p["id"], percent=30, hours=2)
    open_box(api, _box("20% Deposit Bonus").id)
    row = DepositBoost.query.one()
    assert row.percent == 30                                              # the better percentage stays
    assert row.expires_at > utcnow() + timedelta(hours=23)                # but the expiry is extended to 24h
    assert DepositBoost.query.count() == 1


def test_an_expired_boost_is_replaced_and_inactive_boosts_do_not_show(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 100)
    _boost(p["id"], percent=50, hours=-1)
    assert bonus.active_boost(p["id"]) is None and get(api)["boost"] is None
    open_box(api, _box("20% Deposit Bonus").id)
    assert DepositBoost.query.one().percent == 20


# ------------------------------------------------------------------ deposits earn the boost
def test_wallet_payload_shows_balances_and_the_boost_countdown(api, make_player, sandbox_wallet):
    p = make_player(api)
    w = api.get('/api/v1/wallet').get_json()
    assert w["bonus_balance"] == "0.00" and w["boost"] is None
    _boost(p["id"])
    w = api.get('/api/v1/wallet').get_json()
    assert w["boost"]["percent"] == 20 and w["boost"]["seconds_left"] > 0


def test_deposit_20_with_boost_gives_20_wallet_and_4_bonus(api, make_player, sandbox_wallet):
    p = make_player(api)
    _boost(p["id"], 20)
    r = deposit(api, 20, "sbx-d-chime", 1).get_json()
    assert r["status"] == "paid" and r["bonus"] == "4.00" and r["bonus_percent"] == 20
    assert balance(p["id"]) == 2000 and bonus_bal(p["id"]) == 400         # 20 main + 4 bonus (24 total)
    assert api.get('/api/v1/wallet').get_json()["bonus_balance"] == "4.00"
    deposit(api, 20, "sbx-d-chime", 1)                                    # replay: nothing more
    assert balance(p["id"]) == 2000 and bonus_bal(p["id"]) == 400
    kinds = {(e.kind, e.bucket) for e in WalletEntry.query.filter_by(player_id=p["id"])}
    assert kinds == {("deposit", "wallet"), ("deposit_bonus", "bonus")}


def test_boost_applies_to_every_deposit_while_it_lasts(api, make_player, sandbox_wallet):
    p = make_player(api)
    _boost(p["id"], 20)
    deposit(api, 20, "sbx-d-chime", 1)
    deposit(api, 50, "sbx-d-chime", 2)
    assert balance(p["id"]) == 7000 and bonus_bal(p["id"]) == 400 + 1000


def test_no_boost_means_no_bonus_and_expired_boost_means_no_bonus(api, make_player, sandbox_wallet):
    p = make_player(api)
    assert deposit(api, 20, "sbx-d-chime", 1).get_json()["bonus"] is None
    DepositBoost.query.delete()
    _boost(p["id"], 20, hours=-1)
    assert deposit(api, 20, "sbx-d-chime", 2).get_json()["bonus"] is None
    assert bonus_bal(p["id"]) == 0 and balance(p["id"]) == 4000


@pytest.mark.parametrize("amount,expected_cents", [(9.99, 200), (20, 400), (14.99, 300), (1, 20), (25, 500)])
def test_bonus_rounding_is_half_up_on_cents(amount, expected_cents):
    assert ledger.percent_of(ledger.to_cents(amount), 20) == expected_cents


def test_live_deposit_bonus_uses_the_boost_from_when_the_order_was_created(app, api, make_player, pay):
    p = make_player(api)
    _boost(p["id"], 20, hours=1)
    deposit(api, 25, "m-chime")
    order = PaymentOrder.query.one()
    assert order.bonus_percent == 20 and balance(p["id"]) == 0 and bonus_bal(p["id"]) == 0   # nothing before payment
    DepositBoost.query.update({"expires_at": utcnow() - timedelta(minutes=5)})               # boost lapses before payment lands
    db.session.commit()
    payload = {"depositId": order.provider_deposit_id, "status": "paid", "paidAmount": 25.0}
    assert hook(app, "deposit.paid", payload, delivery="d-1").status_code == 200
    assert balance(p["id"]) == 2500 and bonus_bal(p["id"]) == 500                            # snapshot honoured
    hook(app, "deposit.paid", payload, delivery="d-1")
    hook(app, "deposit.paid", payload, delivery="d-2")
    assert balance(p["id"]) == 2500 and bonus_bal(p["id"]) == 500                            # idempotent
    assert WalletEntry.query.filter_by(kind="deposit_bonus").count() == 1


def test_live_deposit_without_a_boost_at_creation_gets_no_bonus_even_if_one_starts_later(app, api, make_player, pay):
    p = make_player(api)
    deposit(api, 25, "m-chime")
    _boost(p["id"], 20)
    order = PaymentOrder.query.one()
    hook(app, "deposit.paid", {"depositId": order.provider_deposit_id, "paidAmount": 25.0}, delivery="d-1")
    assert balance(p["id"]) == 2500 and bonus_bal(p["id"]) == 0


def test_credited_amount_decides_the_bonus_when_the_provider_reports_a_different_amount(app, api, make_player, pay):
    p = make_player(api)
    _boost(p["id"], 20)
    deposit(api, 25, "m-chime")
    order = PaymentOrder.query.one()
    pay.deposit_paid = 20.0
    hook(app, "deposit.paid", {"depositId": order.provider_deposit_id}, delivery="d-1")
    assert balance(p["id"]) == 2000 and bonus_bal(p["id"]) == 400


def test_refund_takes_back_the_deposit_and_its_share_of_the_bonus(app, api, make_player, pay):
    p = make_player(api)
    _boost(p["id"], 20)
    deposit(api, 25, "m-chime")
    order = PaymentOrder.query.one()
    hook(app, "deposit.paid", {"depositId": order.provider_deposit_id, "paidAmount": 25.0}, delivery="p-1")
    assert (balance(p["id"]), bonus_bal(p["id"])) == (2500, 500)
    hook(app, "deposit.refunded", {"depositId": order.provider_deposit_id, "refundAmount": 25.0}, delivery="r-1")
    hook(app, "deposit.refunded", {"depositId": order.provider_deposit_id, "refundAmount": 25.0}, delivery="r-2")
    assert (balance(p["id"]), bonus_bal(p["id"])) == (0, 0)


def test_partial_refund_reverses_the_bonus_proportionally(app, api, make_player, pay):
    p = make_player(api)
    _boost(p["id"], 20)
    deposit(api, 25, "m-chime")
    order = PaymentOrder.query.one()
    hook(app, "deposit.paid", {"depositId": order.provider_deposit_id, "paidAmount": 25.0}, delivery="p-1")
    hook(app, "deposit.refunded", {"depositId": order.provider_deposit_id, "refundAmount": 10.0}, delivery="r-1")
    assert balance(p["id"]) == 1500 and bonus_bal(p["id"]) == 300          # 40% refunded -> 40% of the $5 bonus


def test_bonus_is_never_withdrawable(api, make_player, pay):
    p = make_player(api)
    ledger.credit(p["id"], 5000, "box_reward", "test", "x", bucket="bonus")
    db.session.commit()
    r = api.post('/api/v1/wallet/withdrawals', {"method_id": "w-cash", "amount": 50, "address": "$me", "idempotency_key": KEY(1)})
    assert r.status_code == 402                                           # wallet is empty: the $50 bonus cannot be cashed out
    assert bonus_bal(p["id"]) == 5000


# ------------------------------------------------------------------ spending the bonus balance on a game
def _grant_bonus(pid, cents):
    ledger.credit(pid, cents, "box_reward", "test", f"grant-{pid}-{cents}-{utcnow().timestamp()}", bucket="bonus")
    db.session.commit()


def _access(api):
    assert api.post('/api/v1/games/game-vault/access').status_code == 201


def test_game_state_exposes_both_balances(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    fund(p["id"], 50)
    _grant_bonus(p["id"], 250)
    s = api.get('/api/v1/games/game-vault/access').get_json()
    assert (s["wallet_balance"], s["bonus_balance"], s["bonus_enabled"], s["bonus_min"]) == ("0.50", "2.50", True, "1")


def test_add_bonus_balance_to_a_game_with_one_request(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    _grant_bonus(p["id"], 250)
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "2.50", "source": "bonus", "idempotency_key": KEY(1)})
    assert r.status_code == 201 and r.get_json()["status"] == "completed" and r.get_json()["source"] == "bonus"
    assert bonus_bal(p["id"]) == 0 and balance(p["id"]) == 0               # wallet untouched
    assert api.get('/api/v1/games/game-vault/balance').get_json()["balance"] == "2.50"
    again = api.post('/api/v1/games/game-vault/cash', {"amount": "2.50", "source": "bonus", "idempotency_key": KEY(1)})
    assert again.get_json()["id"] == r.get_json()["id"] and bonus_bal(p["id"]) == 0   # replay: no double spend


def test_bonus_cash_works_without_the_wallet_feature_in_sandbox(api, make_player, game, features):
    features(sandbox=True)                                                # wallet flag stays OFF
    p = make_player(api)
    _access(api)
    _grant_bonus(p["id"], 400)
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "4", "source": "bonus", "idempotency_key": KEY(1)})
    assert r.status_code == 201 and bonus_bal(p["id"]) == 0


def test_bonus_cash_minimum_is_one_dollar_unless_it_is_the_whole_balance(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    _grant_bonus(p["id"], 250)
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "0.50", "source": "bonus", "idempotency_key": KEY(1)}).status_code == 400
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "1", "source": "bonus", "idempotency_key": KEY(2)}).status_code == 201
    assert bonus_bal(p["id"]) == 150
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "0.80", "source": "bonus", "idempotency_key": KEY(3)}).status_code == 400
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "1.50", "source": "bonus", "idempotency_key": KEY(4)}).status_code == 201
    _grant_bonus(p["id"], 80)                                             # $0.80 left: allowed only as "everything"
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "0.80", "source": "bonus", "idempotency_key": KEY(5)}).status_code == 201
    assert bonus_bal(p["id"]) == 0


def test_cannot_spend_more_bonus_than_you_have_and_bad_sources_are_rejected(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    _grant_bonus(p["id"], 300)
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "5", "source": "bonus", "idempotency_key": KEY(1)})
    assert r.status_code == 402 and r.get_json()["code"] == "insufficient_funds" and r.get_json()["source"] == "bonus"
    assert bonus_bal(p["id"]) == 300
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "1", "source": "cash", "idempotency_key": KEY(2)}).status_code == 400
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "-3", "source": "bonus", "idempotency_key": KEY(3)}).status_code == 400
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "NaN", "source": "bonus", "idempotency_key": KEY(4)}).status_code == 400


def test_wallet_source_is_unchanged_and_never_touches_bonus(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    fund(p["id"], 2500)
    _grant_bonus(p["id"], 400)
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": KEY(1)}).status_code == 201
    assert balance(p["id"]) == 1500 and bonus_bal(p["id"]) == 400


class RefusingGateway(FakeGateway):
    def recharge(self, account, amount):
        from app.services.gateway import GatewayError
        raise GatewayError("The game provider could not complete that request. Please try again later.")


class UnknownGateway(FakeGateway):
    def recharge(self, account, amount):
        raise TimeoutError("read timed out")


def _live_bonus(monkeypatch, features, gw):
    features(game_accounts=True)
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: gw)
    monkeypatch.setattr("app.services.gateway.get_gateway", lambda: gw)


def test_failed_recharge_returns_the_bonus_to_the_bonus_balance(api, make_player, game, features, monkeypatch):
    p = make_player(api)
    _live_bonus(monkeypatch, features, RefusingGateway())
    _access(api)
    _grant_bonus(p["id"], 400)
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "4", "source": "bonus", "idempotency_key": KEY(1)})
    assert r.get_json()["status"] == "failed" and bonus_bal(p["id"]) == 400 and balance(p["id"]) == 0


def test_unknown_outcome_holds_bonus_and_staff_resolution_refunds_the_same_bucket(api, make_player, game, features, monkeypatch, staff_client):
    p = make_player(api)
    _live_bonus(monkeypatch, features, UnknownGateway())
    _access(api)
    _grant_bonus(p["id"], 400)
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "4", "source": "bonus", "idempotency_key": KEY(1)}).get_json()
    assert r["status"] == "needs_review" and bonus_bal(p["id"]) == 0
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/cash-requests/{r["id"]}', {"action": "resolve_failed"}).status_code == 200
    assert bonus_bal(p["id"]) == 400 and balance(p["id"]) == 0             # back to BONUS, not the wallet
    assert root.patch(f'/api/v1/admin/cash-requests/{r["id"]}', {"action": "resolve_failed"}).status_code == 409
    assert bonus_bal(p["id"]) == 400


def test_switched_off_provider_blocks_bonus_cash_too(api, make_player, game, sandbox_wallet):
    from app.models import Provider, RemoteProvider
    prov = Provider(name="Off", category=RemoteProvider.CATEGORY2, base_url="https://x.example.com", username="u", password="p", is_active=True)
    db.session.add(prov)
    db.session.flush()
    game.provider_id = prov.id
    db.session.commit()
    p = make_player(api)
    _access(api)
    _grant_bonus(p["id"], 400)
    prov.is_active = False
    db.session.commit()
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "4", "source": "bonus", "idempotency_key": KEY(1)}).status_code == 503
    assert bonus_bal(p["id"]) == 400


# ------------------------------------------------------------------ ledger + migration
def test_buckets_are_independent_in_the_ledger(api, make_player):
    p = make_player(api)
    ledger.credit(p["id"], 1000, "deposit", "o", 1)
    ledger.credit(p["id"], 400, "deposit_bonus", "o", 1, bucket="bonus")
    db.session.commit()
    assert (balance(p["id"]), bonus_bal(p["id"])) == (1000, 400)
    with pytest.raises(ledger.InsufficientFunds):
        ledger.debit(p["id"], 500, "box_reward", "o", 9, bucket="bonus")
    db.session.rollback()
    assert (balance(p["id"]), bonus_bal(p["id"])) == (1000, 400)
    last = WalletEntry.query.filter_by(bucket="bonus").one()
    assert last.balance_after_cents == 400


def test_schema_sync_adds_missing_columns_without_touching_data(app):
    from sqlalchemy import text
    from app.utils.schema import add_missing_columns
    db.session.execute(text("INSERT INTO players (username, email, password_hash, status, role, email_verified, referral_code, wallet_cents, diamonds, bonus_cents, created_at) "
                            "VALUES ('keepme', 'keep@example.com', 'x', 'active', 'player', 0, 'KEEP0001', 1234, 7, 0, CURRENT_TIMESTAMP)"))
    db.session.commit()
    db.session.execute(text("ALTER TABLE players DROP COLUMN bonus_cents"))   # simulate a database from before this feature
    db.session.commit()
    added = add_missing_columns()
    assert "players.bonus_cents" in added
    row = db.session.execute(text("SELECT wallet_cents, diamonds, bonus_cents FROM players WHERE username='keepme'")).one()
    assert tuple(row) == (1234, 7, 0)
    assert add_missing_columns() == []                                         # idempotent
