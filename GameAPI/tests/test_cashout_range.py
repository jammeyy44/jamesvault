"""The cashout range is set only by cash added to this game: not bonus, not wallet deposits that never went into the game."""
import pytest

from app import db
from app.models_site import CashRequest, CatalogGame, GameAccount, WalletEntry
from tests.test_game_access import features  # noqa: F401  (fixture)


@pytest.fixture()
def acct(api, make_player, features):  # noqa: F811
    features(sandbox=True)
    me = make_player(api)
    g = CatalogGame(slug="game-vault", name="Game Vault", category="Slots")
    db.session.add(g)
    db.session.flush()
    a = GameAccount(player_id=me["id"], game_id=g.id, provider_username="gv1", password_enc="x", status="active", sandbox=True)
    db.session.add(a)
    db.session.commit()
    return a


def _add(acct, amount, source, n):
    db.session.add(CashRequest(player_id=acct.player_id, game_account_id=acct.id, amount=amount, source=source,
                               status="completed", idempotency_key=f"k{n}"))
    db.session.commit()


def _preview(api):
    return api.get('/api/v1/games/game-vault/redeem').get_json()


def test_a_wallet_deposit_that_never_went_into_the_game_sets_no_range(api, acct):
    db.session.add(WalletEntry(player_id=acct.player_id, kind="deposit", amount_cents=1000, ref_type="payment_order", ref_id="p1", bucket="wallet"))
    db.session.commit()
    body = _preview(api)
    assert body["rule"] is None and body["can_redeem"] is False and "Add $5" in body["reason"]


def test_bonus_added_to_the_game_sets_no_range(api, acct):
    _add(acct, "10.00", "bonus", 1)
    body = _preview(api)
    assert body["rule"] is None and body["added"] == {"cash": "0.00", "bonus": "10.00", "session": "Bonus"}


def test_the_range_comes_from_the_cash_added_not_cash_plus_bonus(api, acct):
    _add(acct, "10.00", "wallet", 1)
    _add(acct, "20.00", "bonus", 2)      # would have moved the player to a much higher row if it counted
    body = _preview(api)
    assert body["latest_deposit"] == "10.00"
    assert (body["rule"]["min"], body["rule"]["max"]) == ("50.00", "120.00")      # the $10-$16 row, x12 = $120
    assert body["added"] == {"cash": "10.00", "bonus": "20.00", "session": "Cash + Bonus"}


def test_the_most_recent_cash_added_decides(api, acct):
    _add(acct, "5.00", "wallet", 1)
    _add(acct, "30.00", "wallet", 2)
    body = _preview(api)
    assert body["latest_deposit"] == "30.00" and body["rule"]["min"] == "90.00"    # $26-$30 row: x3


# ------------------------------------------------------------------ bonus cashout rule
def _win(acct, amount, n):
    db.session.add(CashRequest(player_id=acct.player_id, game_account_id=acct.id, amount=amount, source="win", sandbox=True,
                               status="completed", idempotency_key=f"w{n}"))
    db.session.commit()


@pytest.mark.parametrize("balance,credit", [(0, 0), (59.99, 0), (60, 10), (75, 10), (90, 10), (90.99, 10), (91, 20), (250, 20)])
def test_bonus_credit_bands(balance, credit):
    from app.services import cashout_rules as rules
    assert rules.bonus_credit(round(balance * 100)) == credit * 100


def test_a_bonus_only_game_is_paid_by_the_bonus_rule(api, acct):
    _add(acct, "5.00", "bonus", 1)
    _win(acct, "70.00", 1)                                  # game balance 75
    body = _preview(api)
    assert body["mode"] == "bonus" and body["rule"] is None and body["can_redeem"] is True
    assert body["payout"] == "10.00" and body["voided"] == "65.00" and body["needs_confirm"] is True


def test_91_and_above_pays_20(api, acct):
    _add(acct, "5.00", "bonus", 1)
    _win(acct, "95.00", 1)                                  # game balance 100
    body = _preview(api)
    assert body["payout"] == "20.00" and body["voided"] == "80.00"


def test_below_60_cannot_cash_out_bonus_winnings(api, acct):
    _add(acct, "5.00", "bonus", 1)
    _win(acct, "40.00", 1)                                  # game balance 45
    body = _preview(api)
    assert body["mode"] == "bonus" and body["can_redeem"] is False and "$60" in body["reason"]


def test_cash_added_keeps_the_cash_table_even_with_bonus(api, acct):
    _add(acct, "10.00", "wallet", 1)
    _add(acct, "5.00", "bonus", 2)
    _win(acct, "60.00", 1)
    body = _preview(api)
    assert body["mode"] == "cash" and body["rule"]["min"] == "50.00"


def test_the_bonus_cash_out_credits_the_wallet_once_and_needs_confirmation(api, acct):
    from app.models_site import Player
    _add(acct, "5.00", "bonus", 1)
    _win(acct, "70.00", 1)
    refused = api.post('/api/v1/games/game-vault/redeem', {"idempotency_key": "bonus-redeem-0001"})
    assert refused.status_code == 409 and refused.get_json()["code"] == "confirm_void"
    ok = api.post('/api/v1/games/game-vault/redeem', {"idempotency_key": "bonus-redeem-0001", "confirm_void": True})
    assert ok.status_code == 201 and ok.get_json()["status"] == "completed" and ok.get_json()["payout"] == "10.00"
    assert db.session.get(Player, acct.player_id).wallet_cents == 1000
    again = api.post('/api/v1/games/game-vault/redeem', {"idempotency_key": "bonus-redeem-0001", "confirm_void": True})
    assert again.get_json()["payout"] == "10.00" and db.session.get(Player, acct.player_id).wallet_cents == 1000   # replay: not paid twice
