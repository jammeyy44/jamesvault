"""Regression tests for the security audit fixes (session revocation, loss-streak race, rate limiting, tokens)."""
from datetime import timedelta

from app import app as flask_app, db
from app.models import Account, AccountType, Token
from app.models_site import PaymentOrder, Player, TaskClaim
from app.utils import auth as auth_utils
from app.utils.auth import hash_service_token, limiter_ident, utcnow

PW = "Sup3rSecret!x"


def _session_cookie(response):
    return [h for h in response.headers.getlist("Set-Cookie") if h.startswith("session=")][-1].split(";")[0]


def _replay(cookie):
    return flask_app.test_client(use_cookies=False).get('/api/v1/auth/me', headers={"Cookie": cookie}).get_json()["player"]


def test_copied_cookie_stops_working_after_logout(api, make_player):
    make_player(api)
    r = api.post('/api/v1/auth/login', {"identifier": "player_one", "password": PW})
    cookie = _session_cookie(r)
    assert _replay(cookie) is not None
    api.post('/api/v1/auth/logout')
    assert _replay(cookie) is None


def test_copied_cookie_stops_working_after_password_change(app, make_player):
    from tests.conftest import Api
    a, b = Api(app.test_client()), Api(app.test_client())
    make_player(a)
    r = b.post('/api/v1/auth/login', {"identifier": "player_one", "password": PW})
    old = _session_cookie(r)
    b.refresh()
    assert _replay(old) is not None
    assert a.post('/api/v1/account/password', {"current_password": PW, "new_password": "An0ther!Pass99"}).status_code == 200
    assert _replay(old) is None
    assert a.get('/api/v1/auth/me').get_json()["player"] is not None  # the device that changed it stays signed in


def test_loss_streak_claim_key_is_the_same_for_a_racing_second_claim(api, make_player):
    me = make_player(api)
    for i in range(5):
        db.session.add(PaymentOrder(player_id=me["id"], method_id="m", method_value="cashapp", method_name="CashApp",
                                    amount_cents=1000, status="paid", idempotency_key=f"rs-{i}"))
    db.session.commit()
    first = api.get('/api/v1/bonus/loss-streak').get_json()["epoch"]
    assert api.get('/api/v1/bonus/loss-streak').get_json()["epoch"] == first
    assert api.post('/api/v1/bonus/loss-streak/claim').status_code == 201
    assert api.get('/api/v1/bonus/loss-streak').get_json()["epoch"] != first
    assert TaskClaim.query.filter_by(player_id=me["id"]).one().claim_key.endswith(first)
    # a duplicate claim for the same streak is refused by the unique key
    db.session.add(TaskClaim(player_id=me["id"], task_key="loss_streak", claim_key=f"loss_streak:{me['id']}:{first}", diamonds=15))
    try:
        db.session.commit()
        raised = False
    except Exception:
        db.session.rollback()
        raised = True
    assert raised
    assert db.session.get(Player, me["id"]).diamonds == 15


def test_spoofed_forwarded_for_does_not_choose_the_rate_limit_bucket(app):
    app.config["TRUSTED_PROXY_COUNT"] = 2
    try:
        with app.test_request_context('/', headers={"X-Forwarded-For": "1.1.1.1, 203.0.113.7, 10.0.0.1"}):
            assert limiter_ident() == "203.0.113.7"
        with app.test_request_context('/', headers={"X-Forwarded-For": "9.9.9.9, 203.0.113.7, 10.0.0.1"}):
            assert limiter_ident() == "203.0.113.7"
    finally:
        app.config["TRUSTED_PROXY_COUNT"] = 0


def test_failed_logins_from_another_address_do_not_lock_the_owner_out(app, make_player):
    from tests.conftest import Api
    owner = Api(app.test_client())
    make_player(owner)
    app.config["RATE_LIMITS_ENABLED"] = True
    try:
        attacker = Api(app.test_client())
        for _ in range(12):
            attacker.post('/api/v1/auth/login', {"identifier": "player_one", "password": "wrong"},
                          headers={"X-Forwarded-For": "198.51.100.9"})
        r = owner.post('/api/v1/auth/login', {"identifier": "player_one", "password": PW}, headers={"X-Forwarded-For": "203.0.113.5"})
        assert r.status_code == 200
    finally:
        app.config["RATE_LIMITS_ENABLED"] = True


def test_rate_limit_table_is_swept(app):
    auth_utils._hits.clear()
    auth_utils._windows.clear()
    with app.app_context():
        for i in range(600):
            auth_utils.rate_limited(f"k{i}", 5, -1)  # negative window: every key is already stale
    assert len(auth_utils._hits) < 600


def test_service_tokens_are_stored_hashed_and_old_plain_ones_still_work(app):
    acct = Account(username="svc-t", email="svc-t@service.invalid", password="x", type=AccountType.STORE)
    db.session.add(acct)
    db.session.flush()
    db.session.add(Token(account_id=acct.id, token=hash_service_token("rawtoken1"), valid_until=utcnow() + timedelta(days=1)))
    db.session.add(Token(account_id=acct.id, token="legacyplain", valid_until=utcnow() + timedelta(days=1)))
    db.session.commit()
    c = app.test_client()
    for raw in ("rawtoken1", "legacyplain"):
        r = c.post('/category1/balance', json={}, headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code != 401, raw
    assert c.post('/category1/balance', json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert Token.query.filter_by(token="rawtoken1").first() is None


def test_missing_field_on_legacy_api_is_a_400_not_a_crash(app):
    acct = Account(username="svc-u", email="svc-u@service.invalid", password="x", type=AccountType.STORE)
    db.session.add(acct)
    db.session.flush()
    db.session.add(Token(account_id=acct.id, token=hash_service_token("tok2"), valid_until=utcnow() + timedelta(days=1)))
    db.session.commit()
    r = app.test_client().post('/category1/add_user', json={}, headers={"Authorization": "Bearer tok2"})
    assert r.status_code in (400, 404), r.status_code


def test_default_secret_key_is_never_used(app):
    assert app.config["SECRET_KEY"] != "mysecretkey"
