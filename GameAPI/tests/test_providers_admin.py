"""Admin provider management, provider off-switch, call logs and ambiguous-outcome reconciliation."""
from decimal import Decimal

import pytest
from sqlalchemy import text

from app import db
from app.models import Provider, RemoteProvider
from app.models_site import CashRequest, CatalogGame, ProviderLog
from app.services.gateway import GatewayError, ProviderGateway
from tests.test_game_access import FakeGateway, features, game, live  # noqa: F401  (fixtures)

NEW = {"name": "New Panel", "category": "CATEGORY1", "base_url": "https://agent.example.com/",
       "username": "agent1", "password": "s3cret-agent-pass"}


def test_provider_management_is_superadmin_only(api, make_player, staff_client):
    assert api.post('/api/v1/admin/providers', NEW).status_code == 401
    make_player(api)
    assert api.post('/api/v1/admin/providers', NEW).status_code == 403
    helper = staff_client("helper", "support")
    assert helper.post('/api/v1/admin/providers', NEW).status_code == 403
    assert helper.get('/api/v1/admin/providers').status_code == 200  # read-only list for the games form
    assert helper.post('/api/v1/admin/providers/1/test').status_code == 403


def test_provider_password_is_encrypted_at_rest_and_never_returned(admin_api):
    r = admin_api.post('/api/v1/admin/providers', NEW)
    assert r.status_code == 201
    body = r.get_data(as_text=True)
    assert "s3cret-agent-pass" not in body and r.get_json()["has_password"] is True
    assert r.get_json()["base_url"] == "https://agent.example.com"
    raw = db.session.execute(text("SELECT password FROM providers")).scalar()
    assert raw.startswith("enc:") and "s3cret-agent-pass" not in raw
    assert Provider.query.one().password == "s3cret-agent-pass"  # adapters still get the plaintext
    assert "s3cret-agent-pass" not in admin_api.get('/api/v1/admin/providers').get_data(as_text=True)


def test_legacy_plaintext_password_still_reads_and_is_encrypted_on_next_write(admin_api):
    db.session.execute(text("INSERT INTO providers (name, category, base_url, username, password, is_active) "
                            "VALUES ('Legacy', 'CATEGORY1', 'https://x.example.com', 'u', 'plain-old', 1)"))
    db.session.commit()
    p = Provider.query.filter_by(name="Legacy").one()
    assert p.password == "plain-old"
    assert admin_api.patch(f'/api/v1/admin/providers/{p.id}', {"password": "rotated-pass"}).status_code == 200
    assert db.session.execute(text("SELECT password FROM providers WHERE name='Legacy'")).scalar().startswith("enc:")


def test_update_keeps_password_when_blank(admin_api):
    pid = admin_api.post('/api/v1/admin/providers', NEW).get_json()["id"]
    assert admin_api.patch(f'/api/v1/admin/providers/{pid}', {"password": "", "username": "agent2"}).status_code == 200
    p = db.session.get(Provider, pid)
    assert (p.username, p.password) == ("agent2", "s3cret-agent-pass")


@pytest.mark.parametrize("url", [
    "http://localhost:8080", "http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5", "http://192.168.1.1", "ftp://agent.example.com", "javascript:alert(1)",
    "https://user:pw@agent.example.com", "http://[::1]/", "http://printer.local", "not a url",
])
def test_provider_url_rejects_internal_and_odd_targets(admin_api, url):
    assert admin_api.post('/api/v1/admin/providers', {**NEW, "base_url": url}).status_code == 400


def test_provider_validation_and_duplicates(admin_api):
    assert admin_api.post('/api/v1/admin/providers', {**NEW, "category": "NOPE"}).status_code == 400
    assert admin_api.post('/api/v1/admin/providers', {**NEW, "password": ""}).status_code == 400
    assert admin_api.post('/api/v1/admin/providers', NEW).status_code == 201
    assert admin_api.post('/api/v1/admin/providers', NEW).status_code == 409


def test_cannot_delete_provider_with_games(admin_api):
    pid = admin_api.post('/api/v1/admin/providers', NEW).get_json()["id"]
    db.session.add(CatalogGame(slug="g", name="G", provider_id=pid))
    db.session.commit()
    assert admin_api.delete(f'/api/v1/admin/providers/{pid}').status_code == 409
    CatalogGame.query.delete()
    db.session.commit()
    assert admin_api.delete(f'/api/v1/admin/providers/{pid}').status_code == 200


def test_test_connection_reports_balance_and_writes_a_log_without_secrets(admin_api, monkeypatch):
    pid = admin_api.post('/api/v1/admin/providers', NEW).get_json()["id"]

    class Svc:
        def get_agent_balance(self):
            return {"message": "ok", "balance": "1234.50"}
    monkeypatch.setattr(ProviderGateway, "_service", lambda self, provider: Svc())
    out = admin_api.post(f'/api/v1/admin/providers/{pid}/test').get_json()
    assert out["ok"] is True and out["agent_balance"] == "1234.50"
    logs = admin_api.get('/api/v1/admin/provider-logs').get_json()["items"]
    assert {l["action"] for l in logs} >= {"test_login", "agent_balance"} and all(l["success"] for l in logs)
    assert "s3cret" not in str(logs)


def test_test_connection_reports_login_failure(admin_api, monkeypatch):
    pid = admin_api.post('/api/v1/admin/providers', NEW).get_json()["id"]

    def boom(self, provider):
        raise GatewayError("The game provider is unavailable right now. Please try again later.")
    monkeypatch.setattr(ProviderGateway, "_service", boom)
    out = admin_api.post(f'/api/v1/admin/providers/{pid}/test').get_json()
    assert out["ok"] is False and "unavailable" in out["message"]
    assert ProviderLog.query.filter_by(success=False).count() == 1


def test_switched_off_provider_receives_no_traffic(admin_api, api, make_player, features):
    pid = admin_api.post('/api/v1/admin/providers', NEW).get_json()["id"]
    g = CatalogGame(slug="panel-game", name="Panel Game", provider_id=pid)
    db.session.add(g)
    db.session.commit()
    assert admin_api.patch(f'/api/v1/admin/providers/{pid}', {"is_active": False}).status_code == 200

    # the gateway itself refuses an inactive provider, before any adapter is constructed
    with pytest.raises(GatewayError):
        ProviderGateway()._service(db.session.get(Provider, pid))

    features(game_accounts=True)
    make_player(api)
    r = api.post('/api/v1/games/panel-game/access')
    assert r.status_code == 503 and r.get_json()["code"] == "maintenance"
    assert api.get('/api/v1/games/panel-game/access').get_json()["game"]["status"] == "maintenance"


def test_games_can_be_assigned_to_a_provider_and_cashout_range_saved(admin_api):
    pid = admin_api.post('/api/v1/admin/providers', NEW).get_json()["id"]
    r = admin_api.post('/api/v1/admin/games', {"slug": "assigned", "name": "Assigned", "provider_id": pid,
                                               "cashout_min": "50", "cashout_max": "80"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["provider_id"] == pid and (body["cashout_min"], body["cashout_max"]) == ("50.00", "80.00")


# ---------------------------------------------------------------- ambiguous outcomes
class AmbiguousGateway(FakeGateway):
    def recharge(self, account, amount):
        raise TimeoutError("read timed out after sending the request")


def _awaiting(api, make_player, game):
    make_player(api)
    api.post('/api/v1/games/game-vault/access')
    return api.post('/api/v1/games/game-vault/cash', {"amount": "20", "idempotency_key": "idem-key-00000001"}).get_json()["id"]


def test_ambiguous_provider_outcome_needs_review_and_is_never_auto_failed(api, make_player, game, live, staff_client, monkeypatch):
    rid = _awaiting(api, make_player, game)
    gw = AmbiguousGateway()
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: gw)
    monkeypatch.setattr("app.services.gateway.get_gateway", lambda: gw)
    root = staff_client("root", "superadmin")
    out = root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"}).get_json()
    assert out["status"] == "needs_review"
    # cannot be re-confirmed (that could double-credit) ...
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"}).status_code == 409
    # ... and a player is not told it failed
    assert CashRequest.query.one().status == "needs_review"
    listed = root.get('/api/v1/admin/cash-requests?status=needs_review').get_json()["items"]
    assert [i["id"] for i in listed] == [rid]


def test_reconciling_needs_review_by_hand(api, make_player, game, live, staff_client, monkeypatch):
    rid = _awaiting(api, make_player, game)
    gw = AmbiguousGateway()
    monkeypatch.setattr("app.services.gateway.get_gateway", lambda: gw)
    root = staff_client("root", "superadmin")
    root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "confirm"})
    helper = staff_client("helper", "support")
    assert helper.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "resolve_completed"}).status_code == 403
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "resolve_completed"}).get_json()["status"] == "completed"
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "resolve_failed"}).status_code == 409


def test_resolve_only_applies_to_needs_review(api, make_player, game, live, staff_client):
    rid = _awaiting(api, make_player, game)
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/cash-requests/{rid}', {"action": "resolve_completed"}).status_code == 409
    assert CashRequest.query.one().status == "awaiting_staff"


def test_adapter_families_are_described_by_game_names(admin_api):
    fams = {f["value"]: f for f in admin_api.get('/api/v1/admin/providers').get_json()["families"]}
    assert fams["CATEGORY1"]["games"] == ["Gameroom", "Cash Machine", "Mr All In One", "Cash Frenzy", "Mafia", "King of Pop"]
    assert fams["CATEGORY2"]["games"] == [] and fams["CATEGORY6"]["games"] == ["Game Vault", "Vegas Sweeps", "Juwa", "Juwa 2.0"]
    assert fams["CATEGORY3"]["games"] == ["Orion Stars", "Panda Master", "Milkyway", "Fire Kirin"]
    assert fams["CATEGORY4"]["games"] == ["River Sweeps"] and fams["CATEGORY5"]["games"] == ["Vblink", "Egame", "Ultra Panda"]
    assert fams["CATEGORY1"]["label"] == "Category 1"


def test_a_provider_you_add_shows_up_in_its_family_without_duplicates(admin_api):
    admin_api.post('/api/v1/admin/providers', {**NEW, "name": "Brand New Game", "category": "CATEGORY3"})
    admin_api.post('/api/v1/admin/providers', {**NEW, "name": "fire kirin", "category": "CATEGORY3"})   # same game, different case
    fams = {f["value"]: f for f in admin_api.get('/api/v1/admin/providers').get_json()["families"]}
    assert fams["CATEGORY3"]["games"] == ["Orion Stars", "Panda Master", "Milkyway", "Fire Kirin", "Brand New Game"]
