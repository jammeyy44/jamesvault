"""Player authentication, CSRF, password reset and account security."""
import hashlib
from datetime import timedelta

from app import db
from app.models_site import PasswordResetToken, Player
from app.utils.auth import utcnow


def test_csrf_required_for_mutations(app):
    client = app.test_client()
    r = client.post('/api/v1/auth/login', json={"identifier": "x", "password": "y"})
    assert r.status_code == 403


def test_register_login_logout(api, make_player):
    player = make_player(api)
    assert api.get('/api/v1/auth/me').get_json()["player"]["username"] == player["username"]
    api.post('/api/v1/auth/logout')
    assert api.get('/api/v1/auth/me').get_json()["player"] is None
    r = api.post('/api/v1/auth/login', {"identifier": "P1@example.com", "password": "Sup3rSecret!x"})
    assert r.status_code == 200


def test_password_is_hashed_and_policy_enforced(api, app):
    r = api.post('/api/v1/auth/register', {"username": "weak_user", "email": "w@example.com",
                                           "password": "short", "accept_terms": True})
    assert r.status_code == 400
    r = api.post('/api/v1/auth/register', {"username": "ok_user", "email": "o@example.com",
                                           "password": "Sup3rSecret!x", "accept_terms": False})
    assert r.status_code == 400  # must accept terms / age
    api.post('/api/v1/auth/register', {"username": "ok_user", "email": "o@example.com",
                                       "password": "Sup3rSecret!x", "accept_terms": True})
    assert "Sup3rSecret" not in Player.query.filter_by(username="ok_user").one().password_hash


def test_duplicate_registration_rejected(api, make_player):
    make_player(api)
    r = api.post('/api/v1/auth/register', {"username": "player_one", "email": "other@example.com",
                                           "password": "Sup3rSecret!x", "accept_terms": True})
    assert r.status_code == 409


def test_login_failure_is_generic_and_rate_limited(api, make_player):
    make_player(api)
    api.post('/api/v1/auth/logout')
    for _ in range(8):
        r = api.post('/api/v1/auth/login', {"identifier": "player_one", "password": "wrong"})
        assert r.status_code == 401
    assert api.post('/api/v1/auth/login', {"identifier": "player_one", "password": "wrong"}).status_code == 429


def test_suspended_player_cannot_log_in(api, make_player):
    make_player(api)
    api.post('/api/v1/auth/logout')
    Player.query.update({"status": "suspended"})
    db.session.commit()
    assert api.post('/api/v1/auth/login', {"identifier": "player_one", "password": "Sup3rSecret!x"}).status_code == 403


def _issue_token(player_id, minutes=30):
    raw = "known-test-token-value-1234567890"
    db.session.add(PasswordResetToken(player_id=player_id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                                      expires_at=utcnow() + timedelta(minutes=minutes)))
    db.session.commit()
    return raw


def test_forgot_password_does_not_reveal_accounts(api, make_player):
    make_player(api)
    a = api.post('/api/v1/auth/forgot', {"email": "p1@example.com"}).get_json()
    b = api.post('/api/v1/auth/forgot', {"email": "nobody@example.com"}).get_json()
    assert a == b
    assert PasswordResetToken.query.count() == 1


def test_reset_token_is_single_use_and_does_not_need_old_password(api, make_player):
    player = make_player(api)
    api.post('/api/v1/auth/logout')
    raw = _issue_token(player["id"])
    r = api.post('/api/v1/auth/reset', {"token": raw, "password": "BrandNewPass99"})
    assert r.status_code == 200
    assert api.post('/api/v1/auth/reset', {"token": raw, "password": "AnotherPass123"}).status_code == 400
    assert api.post('/api/v1/auth/login', {"identifier": "player_one", "password": "BrandNewPass99"}).status_code == 200


def test_expired_reset_token_rejected(api, make_player):
    player = make_player(api)
    raw = _issue_token(player["id"], minutes=-1)
    assert api.post('/api/v1/auth/reset', {"token": raw, "password": "BrandNewPass99"}).status_code == 400


def test_change_password_requires_current(api, make_player):
    make_player(api)
    assert api.post('/api/v1/account/password', {"current_password": "nope", "new_password": "Another1234567"}).status_code == 403
    assert api.post('/api/v1/account/password', {"current_password": "Sup3rSecret!x", "new_password": "Another1234567"}).status_code == 200


def test_private_endpoints_require_login(api):
    for url in ('/api/v1/wallet', '/api/v1/notifications', '/api/v1/referrals/me', '/api/v1/wheel'):
        assert api.get(url).status_code == 401


def test_wallet_is_disabled_and_shows_no_balance(api, make_player):
    make_player(api)
    body = api.get('/api/v1/wallet').get_json()
    assert body["enabled"] is False and body["balance"] is None and body["transactions"] == []


def test_unreachable_database_is_a_clear_503_not_a_crash(api, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def down(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("could not translate host name"))
    monkeypatch.setattr("app.routes.site.player.db.session.flush", down)
    r = api.post('/api/v1/auth/register', {"username": "dbdown_user", "email": "d@example.com",
                                           "password": "Sup3rSecret!x", "accept_terms": True})
    assert r.status_code == 503 and r.get_json()["code"] == "database_unavailable"
    assert "host name" not in r.get_data(as_text=True)  # driver details never reach the client
