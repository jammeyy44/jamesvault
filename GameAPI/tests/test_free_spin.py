"""Free-spin wheel: unlocked by a deposit, one spin per 24h, instant server-chosen prizes."""
from datetime import timedelta

import pytest

from app import db
from app.models_site import DepositBoost, PaymentOrder, Player, WalletEntry, WheelPrize, WheelSpin
from app.services import wallet as ledger, wheel
from app.utils.auth import utcnow
from tests.test_game_access import features  # noqa: F401  (fixture)
from tests.test_wallet import KEY, deposit, sandbox_wallet  # noqa: F401  (fixtures + helper)


@pytest.fixture()
def prizes(app):
    wheel.ensure_default_prizes()
    db.session.commit()


def dia(pid):
    return db.session.get(Player, pid).diamonds   # sandbox accounts start with test diamonds, so tests compare changes


def state(api):
    return api.get('/api/v1/wheel').get_json()


def spin(api):
    return api.post('/api/v1/wheel/spin')


def make_deposit(api, n=1, amount=10):
    return deposit(api, amount, "sbx-d-paypal", n)


def only_prize(kind, value, hours=24):
    """Leave exactly one active prize so the (random) outcome is known."""
    WheelPrize.query.update({"is_active": False})
    p = WheelPrize(kind=kind, value=value, weight=1, boost_hours=hours, label="x")
    db.session.add(p)
    db.session.commit()
    return p


def age_everything(hours):
    """Pretend all deposits and spins happened `hours` ago."""
    delta = timedelta(hours=hours)
    for e in WalletEntry.query.all():
        e.created_at = e.created_at - delta
    for s in WheelSpin.query.all():
        s.created_at = s.created_at - delta
    db.session.commit()


# ------------------------------------------------------------------ defaults
def test_default_prizes_match_the_design_and_are_seeded_once(app):
    wheel.ensure_default_prizes()
    db.session.commit()
    got = sorted((p.kind, p.value) for p in WheelPrize.query)
    assert got == sorted([("diamonds", 1), ("diamonds", 2), ("diamonds", 4), ("freeplay", 200), ("freeplay", 300),
                          ("freeplay", 500), ("boost_percent", 5)])
    wheel.ensure_default_prizes()
    db.session.commit()
    assert WheelPrize.query.count() == 7


def test_leftover_prizes_from_the_old_wheel_are_switched_off(app):
    db.session.add(WheelPrize(label="Old staff-fulfilled prize", weight=3))  # kind/value default: value 0
    db.session.commit()
    wheel.ensure_default_prizes()
    db.session.commit()
    assert WheelPrize.query.filter_by(label="Old staff-fulfilled prize").one().is_active is False


def test_labels_and_odds_are_shown(api, make_player, sandbox_wallet, prizes):
    make_player(api)
    w = state(api)
    assert [p["title"] + " " + p["subtitle"] for p in w["prizes"]] == [
        "1 Diamond", "2 Diamonds", "4 Diamonds", "$2 Freeplay", "$3 Freeplay", "$5 Freeplay", "5% Deposit boost"]
    assert abs(sum(p["odds_percent"] for p in w["prizes"]) - 100) < 0.5


# ------------------------------------------------------------------ unlocking
def test_wheel_requires_login(api, prizes):
    assert api.get('/api/v1/wheel').status_code == 401
    assert spin(api).status_code == 401


def test_wheel_is_locked_while_deposits_are_disabled(api, make_player, prizes):
    make_player(api)
    w = state(api)
    assert w["enabled"] is False and "deposit" in w["reason"].lower() and w["can_spin"] is False
    assert spin(api).status_code == 409


def test_no_deposit_means_no_spin(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    w = state(api)
    assert w["enabled"] is True and w["eligible"] is False and w["can_spin"] is False
    assert "deposit" in w["reason"].lower() and w["closes_in"] is None
    r = spin(api)
    assert r.status_code == 403 and r.get_json()["code"] == "deposit_required"
    assert WheelSpin.query.count() == 0


def test_a_deposit_unlocks_one_spin_with_a_24_hour_countdown(api, make_player, sandbox_wallet, prizes):
    make_player(api)
    make_deposit(api)
    w = state(api)
    assert w["eligible"] and w["can_spin"] and 86000 < w["closes_in"] <= 86400 and w["next_spin_in"] is None


def test_deposits_older_than_24_hours_do_not_unlock(api, make_player, sandbox_wallet, prizes):
    make_player(api)
    make_deposit(api)
    age_everything(25)
    w = state(api)
    assert w["eligible"] is False and w["can_spin"] is False
    assert spin(api).status_code == 403


def test_only_real_wallet_deposits_unlock_the_wheel(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    ledger.credit(p["id"], 5000, "adjustment", "admin", "a")
    ledger.credit(p["id"], 5000, "withdrawal_refund", "withdrawal", "w")
    ledger.credit(p["id"], 5000, "deposit_bonus", "payment_order", "9", bucket="bonus")
    ledger.credit(p["id"], 5000, "box_reward", "player_reward", "7", bucket="bonus")
    db.session.commit()
    assert state(api)["eligible"] is False and spin(api).status_code == 403


def test_a_refunded_deposit_no_longer_unlocks(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    ledger.credit(p["id"], 2000, "deposit", "payment_order", "55")
    db.session.commit()
    assert state(api)["can_spin"] is True
    ledger.debit(p["id"], 2000, "refund", "payment_order", "55", allow_negative=True)
    db.session.commit()
    w = state(api)
    assert w["eligible"] is False and w["can_spin"] is False


def test_a_manually_credited_unmatched_deposit_counts(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    ledger.credit(p["id"], 4000, "deposit", "webhook_deposit", "chime-1")
    db.session.commit()
    assert state(api)["can_spin"] is True


# ------------------------------------------------------------------ prizes apply instantly
def _spin_ready(api, make_player, kind, value, hours=24):
    p = make_player(api)
    make_deposit(api)
    only_prize(kind, value, hours)
    return p


def test_diamond_prize_is_added_instantly(api, make_player, sandbox_wallet, prizes):
    p = _spin_ready(api, make_player, "diamonds", 4)
    before = dia(p["id"])
    r = spin(api)
    assert r.status_code == 201 and r.get_json()["prize"]["kind"] == "diamonds" and "4 diamonds" in r.get_json()["note"]
    assert dia(p["id"]) == before + 4
    assert r.get_json()["state"]["diamonds"] == before + 4


def test_freeplay_prize_goes_to_the_bonus_balance_never_the_wallet(api, make_player, sandbox_wallet, prizes):
    p = _spin_ready(api, make_player, "freeplay", 300)
    before = db.session.get(Player, p["id"]).wallet_cents
    r = spin(api)
    assert r.status_code == 201 and "$3 free play" in r.get_json()["note"]
    me = db.session.get(Player, p["id"])
    assert me.bonus_cents == 300 and me.wallet_cents == before
    entry = WalletEntry.query.filter_by(kind="wheel_reward").one()
    assert (entry.bucket, entry.amount_cents) == ("bonus", 300)


def test_boost_prize_starts_a_deposit_boost(api, make_player, sandbox_wallet, prizes):
    p = _spin_ready(api, make_player, "boost_percent", 5, hours=12)
    r = spin(api)
    assert r.status_code == 201 and r.get_json()["state"]["boost"]["percent"] == 5
    row = DepositBoost.query.one()
    assert row.percent == 5 and timedelta(hours=11) < row.expires_at - utcnow() <= timedelta(hours=12)


def test_a_boost_from_the_wheel_applies_to_the_next_deposit(api, make_player, sandbox_wallet, prizes):
    p = _spin_ready(api, make_player, "boost_percent", 5)
    spin(api)
    r = deposit(api, 20, "sbx-d-chime", 2).get_json()
    assert r["bonus"] == "1.00" and r["bonus_percent"] == 5   # 5% of $20


def test_the_outcome_is_chosen_by_the_server_not_the_client(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    make_deposit(api)
    only_prize("diamonds", 2)
    cheat = WheelPrize(kind="freeplay", value=500, weight=1, label="x", is_active=False)
    db.session.add(cheat)
    db.session.commit()
    r = api.post('/api/v1/wheel/spin', {"prize_id": cheat.id, "prize": "freeplay", "value": 99999})
    assert r.get_json()["prize"]["kind"] == "diamonds"
    assert db.session.get(Player, p["id"]).bonus_cents == 0


def test_weighted_choice_follows_the_weights(monkeypatch, app):
    ps = [WheelPrize(kind="diamonds", value=i + 1, weight=w, label="x") for i, w in enumerate([1, 1, 2])]

    class Fixed:
        def __init__(self, x):
            self.x = x

        def uniform(self, a, b):
            return self.x
    for roll, expected in [(0.4, 1), (1.5, 2), (2.0, 2), (3.9, 3), (4.0, 3)]:
        monkeypatch.setattr(wheel.secrets, "SystemRandom", lambda r=roll: Fixed(r))
        assert wheel.pick(ps).value == expected


def test_inactive_and_zero_weight_prizes_are_never_offered(api, make_player, sandbox_wallet, prizes):
    make_player(api)
    WheelPrize.query.update({"is_active": False})
    a = WheelPrize(kind="diamonds", value=1, weight=1, label="a")
    z = WheelPrize(kind="diamonds", value=9, weight=0, label="z")
    db.session.add_all([a, z])
    db.session.commit()
    assert [p["id"] for p in state(api)["prizes"]] == [a.id]


def test_no_prizes_means_no_spin(api, make_player, sandbox_wallet, prizes):
    make_player(api)
    make_deposit(api)
    WheelPrize.query.update({"is_active": False})
    db.session.commit()
    assert state(api)["can_spin"] is False and spin(api).status_code == 409


# ------------------------------------------------------------------ one spin per 24h
def test_only_one_spin_per_deposit_window(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    make_deposit(api)
    only_prize("diamonds", 1)
    before = dia(p["id"])
    assert spin(api).status_code == 201
    again = spin(api)
    assert again.status_code == 409 and again.get_json()["code"] == "cooldown"
    assert dia(p["id"]) == before + 1 and WheelSpin.query.count() == 1
    w = state(api)
    assert w["can_spin"] is False and 86000 < w["next_spin_in"] <= 86400


def test_a_second_deposit_does_not_skip_the_24_hour_cooldown(api, make_player, sandbox_wallet, prizes):
    make_player(api)
    make_deposit(api, 1)
    only_prize("diamonds", 1)
    assert spin(api).status_code == 201
    make_deposit(api, 2, 20)
    assert state(api)["can_spin"] is False and spin(api).status_code == 409


def test_after_24_hours_a_fresh_deposit_unlocks_the_next_spin(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    make_deposit(api, 1)
    only_prize("diamonds", 1)
    before = dia(p["id"])
    assert spin(api).status_code == 201
    age_everything(25)                      # first spin and deposit are now 25h old
    assert state(api)["can_spin"] is False  # old deposit no longer counts, so this needs a new one
    make_deposit(api, 2, 20)
    assert state(api)["can_spin"] is True
    assert spin(api).status_code == 201 and dia(p["id"]) == before + 2


def test_the_database_blocks_a_second_spin_on_the_same_deposit_even_if_the_cooldown_check_is_raced(api, make_player, sandbox_wallet, prizes):
    p = make_player(api)
    make_deposit(api)
    only_prize("diamonds", 1)
    before = dia(p["id"])
    dep_id = wheel.qualifying_deposit(p["id"]).id
    db.session.add(WheelSpin(player_id=p["id"], prize_id=WheelPrize.query.filter_by(is_active=True).one().id,
                             spin_key=f"{p['id']}:dep{dep_id}", status="applied", created_at=utcnow() - timedelta(hours=30)))
    db.session.commit()
    r = spin(api)  # the cooldown check passes (that spin is 30h old) but the per-deposit key is taken
    assert r.status_code == 409 and dia(p["id"]) == before


def test_spin_history_and_audit(api, make_player, sandbox_wallet, prizes, staff_client):
    make_player(api)
    make_deposit(api)
    only_prize("freeplay", 200)
    spin(api)
    h = state(api)["history"]
    assert h[0]["title"] == "$2" and h[0]["subtitle"] == "Freeplay" and "free play" in h[0]["note"]
    root = staff_client("root", "superadmin")
    assert "wheel.spin" in [a["action"] for a in root.get('/api/v1/admin/audit').get_json()["items"]]


# ------------------------------------------------------------------ admin
def test_admin_manages_prizes_with_validation(prizes, staff_client, api, make_player):
    editor = staff_client("editor", "content")
    ok = editor.post('/api/v1/admin/wheel-prizes', {"kind": "freeplay", "value": 1000, "weight": 5, "boost_hours": 24, "label": ""})
    assert ok.status_code == 201 and ok.get_json()["label"] == "$10 Freeplay"      # auto label
    bad = [{"kind": "freeplay", "value": 0, "weight": 5}, {"kind": "freeplay", "value": 20000, "weight": 5},
           {"kind": "boost_percent", "value": 150, "weight": 5}, {"kind": "diamonds", "value": 3, "weight": 0},
           {"kind": "diamonds", "value": 3, "weight": 5000}, {"kind": "jackpot", "value": 3, "weight": 5},
           {"kind": "diamonds", "value": 3, "weight": 5, "boost_hours": 0}]
    for body in bad:
        assert editor.post('/api/v1/admin/wheel-prizes', {"boost_hours": 24, **body}).status_code == 400, body
    pid = ok.get_json()["id"]
    assert editor.patch(f'/api/v1/admin/wheel-prizes/{pid}', {"value": 0}).status_code == 400
    assert editor.patch(f'/api/v1/admin/wheel-prizes/{pid}', {"weight": 9}).status_code == 200


def test_players_cannot_edit_the_wheel(api, make_player, prizes):
    make_player(api)
    assert api.post('/api/v1/admin/wheel-prizes', {"kind": "diamonds", "value": 5, "weight": 5}).status_code == 403
