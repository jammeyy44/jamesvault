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
