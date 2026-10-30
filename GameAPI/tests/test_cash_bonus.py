"""Verified email: 50% signup bonus on the first cash added to any one game, then 10% on every add. Added straight to the game."""
from app import db
from app.models_site import CashRequest, CatalogGame, Player
from tests.test_bonus_balance import _access, bonus_bal  # noqa: F401
from tests.test_game_access import features, game  # noqa: F401  (fixtures)
from tests.test_wallet import KEY, balance, fund, sandbox_wallet  # noqa: F401


def _verify(pid):
    db.session.get(Player, pid).email_verified = True
    db.session.commit()


def _cash(api, amount, n):
    return api.post('/api/v1/games/game-vault/cash', {"amount": amount, "source": "wallet", "idempotency_key": KEY(n)})


def _game_balance(api):
    return api.get('/api/v1/games/game-vault/balance').get_json()["balance"]


def test_unverified_email_gets_no_bonus_and_is_told_to_verify(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    fund(p["id"], 5000)
    info = api.get('/api/v1/games/game-vault/access').get_json()["cash_bonus"]
    assert info["email_verified"] is False and info["percent"] == 0 and info["signup_percent"] == 50 and info["regular_percent"] == 10
    r = _cash(api, "20.00", 1).get_json()
    assert r["bonus"] == "0.00" and _game_balance(api) == "20.00"


def test_verified_email_gets_50_percent_signup_bonus_straight_into_the_game(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    _verify(p["id"])
    fund(p["id"], 5000)
    assert api.get('/api/v1/games/game-vault/access').get_json()["cash_bonus"]["percent"] == 50
    r = _cash(api, "20.00", 1)
    body = r.get_json()
    assert r.status_code == 201 and body["status"] == "completed" and body["bonus"] == "10.00" and body["bonus_kind"] == "signup"
    assert _game_balance(api) == "30.00"                    # $20 cash + $10 bonus, in the game
    assert balance(p["id"]) == 3000 and bonus_bal(p["id"]) == 0   # only the $20 left the wallet; nothing went to the bonus balance
    assert CashRequest.query.one().amount == 20            # the cashout range still looks at the cash added, not the bonus


def test_after_the_signup_bonus_every_add_earns_10_percent(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    _verify(p["id"])
    fund(p["id"], 10000)
    assert _cash(api, "10.00", 1).get_json()["bonus"] == "5.00"
    second = _cash(api, "10.00", 2)
    assert second.status_code == 409                       # a game that still has money cannot be topped up
    # play it away (fake provider keeps a running total, so use a second login-free approach: the rule is on the server)
    info = api.get('/api/v1/games/game-vault/access').get_json()["cash_bonus"]
    assert info["kind"] == "regular" and info["percent"] == 10 and info["signup_available"] is False


def test_signup_bonus_is_replayed_safely_and_only_granted_once(api, make_player, game, sandbox_wallet):
    p = make_player(api)
    _access(api)
    _verify(p["id"])
    fund(p["id"], 10000)
    first = _cash(api, "10.00", 1).get_json()
    again = _cash(api, "10.00", 1).get_json()
    assert again["id"] == first["id"] and _game_balance(api) == "15.00"
    assert db.session.get(Player, p["id"]).signup_bonus_claimed_at is not None


def test_a_failed_add_gives_the_signup_bonus_back(api, make_player, game, sandbox_wallet, monkeypatch):
    from app.services.gateway import GatewayError
    p = make_player(api)
    _access(api)
    _verify(p["id"])
    fund(p["id"], 5000)
    real = {}

    class Boom:
        name = "boom"
        def get_balance(self, a): return 0
        def recharge(self, a, amount): raise GatewayError("no")
    import app.routes.site.accounts as acc
    real["gw"] = acc.get_gateway
    monkeypatch.setattr(acc, "get_gateway", lambda: Boom())
    r = _cash(api, "10.00", 1).get_json()
    assert r["status"] == "failed" and r["bonus"] == "0.00"
    assert balance(p["id"]) == 5000                         # refunded
    assert db.session.get(Player, p["id"]).signup_bonus_claimed_at is None
    assert api.get('/api/v1/games/game-vault/access').get_json()["cash_bonus"]["percent"] == 50


def test_bonus_balance_spending_earns_no_extra_bonus(api, make_player, game, sandbox_wallet):
    from app.services import wallet as ledger
    from app.utils.auth import utcnow
    p = make_player(api)
    _access(api)
    _verify(p["id"])
    ledger.credit(p["id"], 1000, "box_reward", "test", f"g-{utcnow().timestamp()}", bucket="bonus")
    db.session.commit()
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "10.00", "source": "bonus", "idempotency_key": KEY(1)}).get_json()
    assert r["bonus"] == "0.00" and _game_balance(api) == "10.00"


def test_admin_sees_everything_about_a_player(api, make_player, game, sandbox_wallet, staff_client):
    from app.models_site import Coupon, CouponRedemption
    p = make_player(api)
    _access(api)
    _verify(p["id"])
    fund(p["id"], 5000)
    _cash(api, "20.00", 1)
    c = Coupon(code="HELLO5", reward_cents=500, scope="many")
    db.session.add(c)
    db.session.flush()
    db.session.add(CouponRedemption(coupon_id=c.id, player_id=p["id"], amount_cents=500))
    db.session.commit()

    r = staff_client("helper", "support").get(f'/api/v1/admin/players/{p["id"]}/profile')
    assert r.status_code == 200
    d = r.get_json()
    assert d["player"]["email_verified"] is True and d["player"]["wallet"] == "30.00"
    assert d["signup_bonus"]["claimed"] is True and d["signup_bonus"]["game"] == "Game Vault"
    assert d["signup_bonus"]["cash_added"] == "20.00" and d["signup_bonus"]["bonus_amount"] == "10.00"
    g = d["games"][0]
    assert g["game"] == "Game Vault" and g["cash_added"] == "20.00" and g["bonus_added"] == "10.00"
    assert d["coupons"][0]["code"] == "HELLO5" and d["totals"]["coupon_total"] == "5.00"
    assert "password" not in str(d).lower()
    # players cannot open it
    assert api.get(f'/api/v1/admin/players/{p["id"]}/profile').status_code == 403
