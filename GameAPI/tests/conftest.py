import os
import tempfile

import pytest

_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'test.db')}"
os.environ["JV_ENV"] = "test"
# Tests must not depend on a developer's .env: every flag/secret starts from its default and tests switch things on explicitly.
for _k in ("JV_ENABLE_WALLET", "JV_ENABLE_GAME_ACCOUNTS", "JV_ENABLE_CASH_REQUESTS", "JV_SANDBOX"):
    os.environ[_k] = "false"
os.environ["PAYDORA_API_KEY"] = ""

from app import app as flask_app, db  # noqa: E402
from app.utils import auth as auth_utils  # noqa: E402


@pytest.fixture()
def app():
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        auth_utils._hits.clear()
        yield flask_app
        db.session.remove()


class Api:
    """Test client wrapper that handles the CSRF handshake."""

    def __init__(self, client):
        self.c = client
        self.refresh()

    def refresh(self):
        self.token = self.c.get('/api/v1/csrf').get_json()['csrf_token']

    def _h(self, csrf=True):
        return {"X-CSRF-Token": self.token} if csrf else {}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, csrf=True, **kw):
        r = self.c.post(url, json=json or {}, headers={**self._h(csrf), **kw.pop("headers", {})}, **kw)
        body = r.get_json(silent=True)
        if isinstance(body, dict) and body.get("csrf_token"):
            self.token = body["csrf_token"]
        return r

    def patch(self, url, json=None):
        return self.c.patch(url, json=json or {}, headers=self._h())

    def put(self, url, json=None):
        return self.c.put(url, json=json or {}, headers=self._h())

    def delete(self, url):
        return self.c.delete(url, headers=self._h())


@pytest.fixture()
def api(app):
    return Api(app.test_client())


@pytest.fixture()
def make_player(app):
    def _make(api_client, username="player_one", email="p1@example.com", password="Sup3rSecret!x", **extra):
        r = api_client.post('/api/v1/auth/register', {
            "username": username, "email": email, "password": password, "accept_terms": True, **extra})
        assert r.status_code == 201, r.get_json()
        api_client.refresh()
        return r.get_json()["player"]
    return _make


def _staff_client(app, username, role):
    from app.models_site import Player
    player = Player(username=username, email=f"{username}@staff.example.com", role=role)
    player.set_password("StaffPass123!")
    db.session.add(player)
    db.session.commit()
    client = Api(app.test_client())
    r = client.post('/api/v1/auth/login', {"identifier": username, "password": "StaffPass123!"})
    assert r.status_code == 200
    assert r.get_json()["player"]["is_admin"] is True
    return client


@pytest.fixture()
def staff_client(app):
    """Factory: staff_client("name", "support") -> logged-in client (same login as players)."""
    return lambda username, role: _staff_client(app, username, role)


@pytest.fixture()
def admin_api(app):
    return _staff_client(app, "root", "superadmin")
