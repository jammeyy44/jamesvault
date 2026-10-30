"""Get access (provider account), login details, balance and Add Cash."""
from decimal import Decimal

import pytest

from app import db
from app.models_site import CashRequest, CatalogGame, GameAccount
from app.services.gateway import GatewayError


@pytest.fixture()
def features(app):
    """Toggle feature flags for one test and restore them afterwards."""
    original = dict(app.config["FEATURES"])

    def _set(**flags):
        app.config["FEATURES"].update(flags)
    yield _set
    app.config["FEATURES"].clear()
    app.config["FEATURES"].update(original)


@pytest.fixture()
def game(app):
    g = CatalogGame(slug="game-vault", name="Game Vault", category="Category 2")
    db.session.add(g)
    db.session.commit()
    return g


def _key(n=1):
    return f"idem-key-{n:08d}"


def test_everything_reports_unavailable_when_disabled(api, make_player, game, features):
    features(game_accounts=False, sandbox=False)
    make_player(api)
    r = api.post('/api/v1/games/game-vault/access')
    assert r.status_code == 501 and r.get_json()["code"] == "accounts_unavailable"
    state = api.get('/api/v1/games/game-vault/access').get_json()
    assert state["mode"] == "disabled" and state["account"] is None and state["cash_enabled"] is False


def test_access_requires_login(api, game, features):
    features(sandbox=True)
    assert api.post('/api/v1/games/game-vault/access').status_code == 401
    assert api.get('/api/v1/games/game-vault/access/credentials').status_code == 401


def test_sandbox_get_access_is_idempotent_and_password_is_encrypted(api, make_player, game, features):
    features(sandbox=True)
    make_player(api)
    first = api.post('/api/v1/games/game-vault/access')
    assert first.status_code == 201
    body = first.get_json()
    assert body["sandbox_notice"] and body["account"]["username"].startswith("ga")
    again = api.post('/api/v1/games/game-vault/access')
    assert again.status_code == 200 and again.get_json()["account"]["username"] == body["account"]["username"]
    assert GameAccount.query.count() == 1

    creds = api.get('/api/v1/games/game-vault/access/credentials').get_json()
    assert creds["username"] == body["account"]["username"] and len(creds["password"]) == 10
    stored = GameAccount.query.one().password_enc
    assert creds["password"] not in stored


def test_credentials_are_private_to_their_owner(app, api, make_player, game, features):
    from tests.conftest import Api
    features(sandbox=True)
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    other = Api(app.test_client())
    make_player(other, username="someone_else", email="s@example.com")
    assert other.get('/api/v1/games/game-vault/access/credentials').status_code == 404
    assert other.get('/api/v1/games/game-vault/balance').status_code == 404
    assert other.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": _key()}).status_code == 404


def test_maintenance_blocks_new_access(api, make_player, game, features):
    features(sandbox=True)
    game.status = "maintenance"
    db.session.commit()
    make_player(api)
    assert api.post('/api/v1/games/game-vault/access').status_code == 503


def test_sandbox_add_cash_updates_balance_and_replays_never_double_apply(api, make_player, game, features):
    features(sandbox=True)
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    assert api.get('/api/v1/games/game-vault/balance').get_json()["balance"] == "0.00"

    r = api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": _key(1)})
    assert r.status_code == 201 and r.get_json()["status"] == "completed" and r.get_json()["sandbox"] is True
    again = api.post('/api/v1/games/game-vault/cash', {"amount": "10", "idempotency_key": _key(1)})
    assert again.status_code == 200 and again.get_json()["id"] == r.get_json()["id"]
    assert CashRequest.query.count() == 1
    assert api.get('/api/v1/games/game-vault/balance').get_json()["balance"] == "10.00"

    api.post('/api/v1/games/game-vault/cash', {"amount": "25.50", "idempotency_key": _key(2)})
    assert api.get('/api/v1/games/game-vault/balance').get_json()["balance"] == "35.50"


@pytest.mark.parametrize("amount", ["0", "-5", "4.99", "501", "10.005", "abc", "NaN", "Infinity", None])
def test_add_cash_rejects_bad_amounts(api, make_player, game, features, amount):
    features(sandbox=True)
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    r = api.post('/api/v1/games/game-vault/cash', {"amount": amount, "idempotency_key": _key()})
    assert r.status_code == 400
    assert CashRequest.query.count() == 0


def test_add_cash_requires_idempotency_key(api, make_player, game, features):
    features(sandbox=True)
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    assert api.post('/api/v1/games/game-vault/cash', {"amount": "10"}).status_code == 400


def test_cashout_range_only_shown_when_admin_sets_it(api, make_player, game, features):
    features(sandbox=True)
    make_player(api)
    assert api.get('/api/v1/games/game-vault/access').get_json()["cash"]["cashout_min"] is None
    game.cashout_min, game.cashout_max = Decimal("50"), Decimal("80")
    db.session.commit()
    cash = api.get('/api/v1/games/game-vault/access').get_json()["cash"]
    assert (cash["cashout_min"], cash["cashout_max"]) == ("50.00", "80.00")


# ------------------------------------------------------------------ live mode with a fake provider gateway
class FakeGateway:
    name = "fake"

    def __init__(self):
        self.created, self.recharges, self.fail_recharge, self.fail_create = [], [], False, False

    def create_account(self, game, username, password):
        if self.fail_create:
            raise GatewayError("The game provider is unavailable right now. Please try again later.")
        self.created.append(username)

    def get_balance(self, account):
        return sum((a for _, a in self.recharges), Decimal("0.00"))

    def recharge(self, account, amount):
        if self.fail_recharge:
            raise GatewayError("The game provider could not complete that request. Please try again later.")
        self.recharges.append((account.provider_username, amount))


@pytest.fixture()
def live(monkeypatch, features):
    gw = FakeGateway()
    features(game_accounts=True, cash_requests=True)
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: gw)
    monkeypatch.setattr("app.services.gateway.get_gateway", lambda: gw)
    return gw


def test_live_provider_failure_creates_no_account_and_can_be_retried(api, make_player, game, live):
    make_player(api)
    live.fail_create = True
    r = api.post('/api/v1/games/game-vault/access')
    assert r.status_code == 502 and GameAccount.query.count() == 0
    live.fail_create = False
    assert api.post('/api/v1/games/game-vault/access').status_code == 201
    assert len(live.created) == 1


def test_live_cash_waits_for_staff_and_recharges_exactly_once(api, make_player, game, live, staff_client):
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "20", "idempotency_key": _key()})
    assert r.status_code == 201 and r.get_json()["status"] == "awaiting_staff" and r.get_json()["sandbox"] is False
    assert live.recharges == []  # nothing credited before staff confirm payment
    assert api.get('/api/v1/games/game-vault/balance').get_json()["balance"] == "0.00"

    helper = staff_client("helper", "support")
    rid = r.get_json()["id"]
    assert helper.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"}).status_code == 403  # money = superadmin only
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"}).get_json()["status"] == "completed"
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"}).status_code == 409
    assert len(live.recharges) == 1 and live.recharges[0][1] == Decimal("20.00")
    assert api.get('/api/v1/games/game-vault/balance').get_json()["balance"] == "20.00"


def test_live_recharge_failure_is_recorded_and_not_retried_blindly(api, make_player, game, live, staff_client):
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    rid = api.post('/api/v1/games/game-vault/cash', {"amount": "20", "idempotency_key": _key()}).get_json()["id"]
    live.fail_recharge = True
    root = staff_client("root", "superadmin")
    out = root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"}).get_json()
    assert out["status"] == "failed" and out["note"]
    live.fail_recharge = False
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"}).status_code == 409
    assert live.recharges == []


def test_live_reject_never_calls_provider(api, make_player, game, live, staff_client):
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    rid = api.post('/api/v1/games/game-vault/cash', {"amount": "20", "idempotency_key": _key()}).get_json()["id"]
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "reject"}).get_json()["status"] == "rejected"
    assert live.recharges == []


def test_live_cash_disabled_without_cash_flag(api, make_player, game, live, features):
    features(cash_requests=False)
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    r = api.post('/api/v1/games/game-vault/cash', {"amount": "20", "idempotency_key": _key()})
    assert r.status_code == 501 and r.get_json()["code"] == "cash_unavailable"
