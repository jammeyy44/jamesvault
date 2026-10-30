"""The legacy provider endpoints must no longer be reachable anonymously."""
from datetime import timedelta

from app import db
from app.models import Account, AccountType, Token
from app.utils.auth import utcnow

PROVIDER_ROUTES = [
    ('post', '/category1/login'), ('post', '/category2/recharge'), ('post', '/category3/redeem'),
    ('post', '/category4/add_user'), ('post', '/category5/reset_password'), ('post', '/vblink/login'),
]


def test_provider_routes_require_authentication(app):
    client = app.test_client()
    for method, url in PROVIDER_ROUTES:
        assert getattr(client, method)(url, json={}).status_code == 401, url


def test_valid_api_token_passes_auth_but_expired_or_revoked_does_not(app):
    acct = Account(username="svc", email="svc@service.invalid", password="x", type=AccountType.STORE)
    db.session.add(acct)
    db.session.flush()
    db.session.add_all([
        Token(account_id=acct.id, token="good", valid_until=utcnow() + timedelta(days=1)),
        Token(account_id=acct.id, token="old", valid_until=utcnow() - timedelta(days=1)),
        Token(account_id=acct.id, token="gone", valid_until=utcnow() + timedelta(days=1), is_deleted=True),
    ])
    db.session.commit()
    client = app.test_client()
    ok = client.post('/vblink/login', json={}, headers={"Authorization": "Bearer good"})
    assert ok.status_code == 501  # authenticated; endpoint honestly reports "not implemented"
    for bad in ("old", "gone", "nope"):
        assert client.post('/vblink/login', json={}, headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    assert Token.query.filter_by(token="good").one().usage_count == 1


def test_superadmin_player_session_can_reach_provider_routes_but_players_cannot(api, staff_client, make_player):
    make_player(api)
    assert api.post('/vblink/login', json={}).status_code == 401  # signed-in ordinary player
    root = staff_client("root", "superadmin")
    assert root.post('/vblink/login', json={}).status_code == 501
