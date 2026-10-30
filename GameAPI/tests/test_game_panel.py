"""Game panel: CAPTCHA handling, reset password, remove login, thumbnails and the download link."""
import base64
import io
import os

import pytest

from app import db
from app.models import Provider, RemoteProvider
from app.models_site import CashRequest, CatalogGame, GameAccount
from app.services.base_service import CaptchaError
from app.services.category2_service import Category2Service
from app.services.gateway import GatewayError, ProviderGateway, SandboxGateway
from tests.test_game_access import features, game  # noqa: F401  (fixtures)
from tests.test_wallet import KEY  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBP" + b"0" * 64


@pytest.fixture()
def uploads(app, tmp_path):
    old = app.config["UPLOAD_DIR"]
    app.config["UPLOAD_DIR"] = str(tmp_path)
    yield tmp_path
    app.config["UPLOAD_DIR"] = old


@pytest.fixture()
def sandbox(features):
    features(sandbox=True)


def get_access(api, slug="game-vault"):
    assert api.post(f'/api/v1/games/{slug}/access').status_code == 201


def creds(api, slug="game-vault"):
    return api.get(f'/api/v1/games/{slug}/access/credentials').get_json()


# ------------------------------------------------------------------ CAPTCHA
class FakeResp:
    def __init__(self, status=200, content=PNG):
        self.status_code, self.content = status, content


class FakeSession:
    def __init__(self, resp=None):
        self.resp, self.urls = resp or FakeResp(), []

    def get(self, url, **kw):
        self.urls.append(url)
        return self.resp


class FakeSolver:
    seen = []

    def __init__(self, key):
        self.key = key

    def normal(self, arg):
        FakeSolver.seen.append((self.key, arg))
        return {"code": "ab12"}


def _service(app):
    return Category2Service(Provider(name="Game Vault", category=RemoteProvider.CATEGORY2, base_url="https://gv.example.com",
                                     username="u", password="p"))


def test_a_missing_or_placeholder_captcha_key_is_reported_not_attempted(app, monkeypatch):
    svc = _service(app)
    svc.session = FakeSession()
    for key in (None, "", "   ", "your_actual_2captcha_api_key", "your-2captcha-api-key-here", "your_2captcha_api_key"):
        app.config["CAPTCHA_API_KEY"] = key
        with pytest.raises(CaptchaError, match="CAPTCHA_API_KEY is not set"):
            svc.solve_image_captcha("https://gv.example.com/captcha")
    assert svc.session.urls == []                                    # never even fetched the image


def test_the_image_is_fetched_in_the_login_session_and_sent_to_2captcha_as_base64(app, monkeypatch):
    app.config["CAPTCHA_API_KEY"] = "real-key-123"
    monkeypatch.setattr("twocaptcha.TwoCaptcha", FakeSolver)
    FakeSolver.seen = []
    svc = _service(app)
    svc.session = FakeSession(FakeResp(200, PNG))
    assert svc.solve_image_captcha("https://gv.example.com/api/agent/captcha?t=1") == "ab12"
    assert svc.session.urls == ["https://gv.example.com/api/agent/captcha?t=1"]    # same session = same cookies as the login
    key, arg = FakeSolver.seen[0]
    assert key == "real-key-123" and not arg.startswith("http") and base64.b64decode(arg) == PNG   # image bytes, not a URL
    assert "." not in arg and len(arg) > 50                                         # the shape the 2Captcha client treats as base64


@pytest.mark.parametrize("status", [403, 404, 500])
def test_a_refused_captcha_image_is_reported_with_the_status(app, monkeypatch, status):
    app.config["CAPTCHA_API_KEY"] = "real-key-123"
    monkeypatch.setattr("twocaptcha.TwoCaptcha", FakeSolver)
    FakeSolver.seen = []
    svc = _service(app)
    svc.session = FakeSession(FakeResp(status, b"nope"))
    with pytest.raises(CaptchaError, match=f"HTTP {status}"):
        svc.solve_image_captcha("https://gv.example.com/captcha")
    assert FakeSolver.seen == []


def test_2captcha_failures_are_wrapped(app, monkeypatch):
    app.config["CAPTCHA_API_KEY"] = "real-key-123"

    class Boom(FakeSolver):
        def normal(self, arg):
            raise RuntimeError("ERROR_ZERO_BALANCE")
    monkeypatch.setattr("twocaptcha.TwoCaptcha", Boom)
    svc = _service(app)
    svc.session = FakeSession()
    with pytest.raises(CaptchaError, match="ERROR_ZERO_BALANCE"):
        svc.solve_image_captcha("https://gv.example.com/captcha")


def test_login_reports_why_it_failed_and_the_admin_test_shows_it(app, admin_api):
    app.config["CAPTCHA_API_KEY"] = ""
    login = _service(app).login("agent", "pw")
    assert login["error"].startswith("CAPTCHA_API_KEY is not set")
    pid = admin_api.post('/api/v1/admin/providers', {"name": "GV", "category": "CATEGORY2", "base_url": "https://gv.example.com",
                                                    "username": "u", "password": "p"}).get_json()["id"]
    out = admin_api.post(f'/api/v1/admin/providers/{pid}/test').get_json()
    assert out["ok"] is False and "CAPTCHA_API_KEY is not set" in out["message"] and "unavailable" in out["message"]
    logs = admin_api.get('/api/v1/admin/provider-logs').get_json()["items"]
    assert any("CAPTCHA_API_KEY" in (l["detail"] or "") for l in logs)


def test_no_captcha_key_is_hard_coded_in_the_adapters():
    base = os.path.join(os.path.dirname(__file__), "..", "app", "services")
    for name in os.listdir(base):
        if name.endswith(".py"):
            text = open(os.path.join(base, name), encoding="utf-8").read()
            assert "cdfa431906375d3df98956d07371248a" not in text, name


# ------------------------------------------------------------------ reset password
def test_reset_password_gives_a_new_working_password(api, make_player, game, sandbox):
    make_player(api)
    get_access(api)
    before = creds(api)
    assert api.post('/api/v1/games/game-vault/access/reset-password').status_code == 200
    after = creds(api)
    assert after["username"] == before["username"] and after["password"] != before["password"] and len(after["password"]) == 10


def test_reset_password_needs_login_and_an_account(api, make_player, game, sandbox):
    assert api.post('/api/v1/games/game-vault/access/reset-password').status_code == 401
    make_player(api)
    assert api.post('/api/v1/games/game-vault/access/reset-password').status_code == 404


class RefusingReset(SandboxGateway):
    def reset_password(self, account, new_password):
        raise GatewayError("The game provider could not complete that request. Please try again later.")


class UnclearReset(SandboxGateway):
    def reset_password(self, account, new_password):
        raise TimeoutError("read timed out")


def test_a_refused_or_unclear_reset_keeps_the_old_password(api, make_player, game, sandbox, monkeypatch):
    make_player(api)
    get_access(api)
    before = creds(api)["password"]
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: RefusingReset())
    r = api.post('/api/v1/games/game-vault/access/reset-password')
    assert r.status_code == 502 and r.get_json()["code"] == "provider_error" and creds(api)["password"] == before
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: UnclearReset())
    r = api.post('/api/v1/games/game-vault/access/reset-password')
    assert r.status_code == 502 and r.get_json()["code"] == "provider_unclear" and creds(api)["password"] == before


def test_reset_password_is_rate_limited(api, make_player, game, sandbox):
    make_player(api)
    get_access(api)
    codes = [api.post('/api/v1/games/game-vault/access/reset-password').status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_players_cannot_reset_each_others_logins(app, api, make_player, game, sandbox):
    from tests.conftest import Api
    make_player(api)
    get_access(api)
    other = Api(app.test_client())
    make_player(other, username="someone_else", email="s@example.com")
    assert other.post('/api/v1/games/game-vault/access/reset-password').status_code == 404


# ------------------------------------------------------------------ remove login
def test_an_empty_login_can_be_removed_and_a_fresh_one_created_later(api, make_player, game, sandbox):
    make_player(api)
    get_access(api)
    old = creds(api)
    assert api.delete('/api/v1/games/game-vault/access').status_code == 200
    assert api.get('/api/v1/games/game-vault/access').get_json()["account"] is None
    assert api.get('/api/v1/games/game-vault/access/credentials').status_code == 404
    assert GameAccount.query.count() == 1 and GameAccount.query.one().status == "removed"
    assert api.post('/api/v1/games/game-vault/access').status_code == 201      # coming back creates a NEW login
    new = creds(api)
    assert new["username"] != old["username"] and GameAccount.query.count() == 1


def test_a_login_holding_money_cannot_be_removed(api, make_player, game, sandbox):
    make_player(api)
    get_access(api)
    api.post('/api/v1/games/game-vault/sandbox/win', {"amount": "25"})
    r = api.delete('/api/v1/games/game-vault/access')
    assert r.status_code == 409 and r.get_json()["code"] == "has_balance" and "$25.00" in r.get_json()["error"]
    assert GameAccount.query.one().status == "active"


def test_a_login_with_a_pending_request_cannot_be_removed(api, make_player, game, sandbox):
    p = make_player(api)
    get_access(api)
    acct = GameAccount.query.one()
    db.session.add(CashRequest(player_id=p["id"], game_account_id=acct.id, amount=10, idempotency_key=KEY(1), status="awaiting_staff"))
    db.session.commit()
    r = api.delete('/api/v1/games/game-vault/access')
    assert r.status_code == 409 and r.get_json()["code"] == "pending" and GameAccount.query.one().status == "active"


class BrokenBalance(SandboxGateway):
    def get_balance(self, account):
        raise TimeoutError("boom")


def test_if_the_balance_cannot_be_verified_nothing_is_removed(api, make_player, game, sandbox, monkeypatch):
    make_player(api)
    get_access(api)
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: BrokenBalance())
    r = api.delete('/api/v1/games/game-vault/access')
    assert r.status_code == 502 and GameAccount.query.one().status == "active"


def test_a_failed_recreate_leaves_the_removed_login_removed(api, make_player, game, sandbox, monkeypatch):
    make_player(api)
    get_access(api)
    api.delete('/api/v1/games/game-vault/access')

    class NoCreate(SandboxGateway):
        def create_account(self, game, username, password):
            raise GatewayError("The game provider is unavailable right now. Please try again later.")
    monkeypatch.setattr("app.routes.site.accounts.get_gateway", lambda: NoCreate())
    assert api.post('/api/v1/games/game-vault/access').status_code == 502
    assert GameAccount.query.one().status == "removed"


# ------------------------------------------------------------------ download link + thumbnail
def upload(client, gid, data, name="thumb.png"):
    return client.c.post(f'/api/v1/admin/games/{gid}/thumbnail', data={"file": (io.BytesIO(data), name)},
                         headers={"X-CSRF-Token": client.token}, content_type="multipart/form-data")


def test_download_url_is_validated_and_exposed(api, make_player, game, sandbox, staff_client):
    editor = staff_client("editor", "content")
    gid = CatalogGame.query.one().id
    for bad in ("javascript:alert(1)", "//evil.com/x", "ftp://x.com/a", "https://x.com/a b", 'https://x.com/"onload=1', "data:text/html,hi"):
        assert editor.patch(f'/api/v1/admin/games/{gid}', {"download_url": bad}).status_code == 400, bad
    assert editor.patch(f'/api/v1/admin/games/{gid}', {"download_url": "https://dl.example.com/game.apk"}).status_code == 200
    make_player(api)
    get_access(api)
    assert api.get('/api/v1/games/game-vault/access').get_json()["game"]["download_url"] == "https://dl.example.com/game.apk"
    assert api.get('/api/v1/games').get_json()["items"][0]["download_url"] == "https://dl.example.com/game.apk"


def test_image_url_accepts_https_or_our_uploads_only(game, staff_client):
    editor = staff_client("editor", "content")
    gid = CatalogGame.query.one().id
    for bad in ("javascript:alert(1)", "//evil.com/a.png", "/etc/passwd", "/uploads/other/x.png", "data:image/png;base64,AAAA"):
        assert editor.patch(f'/api/v1/admin/games/{gid}', {"image_url": bad}).status_code == 400, bad
    for good in ("https://cdn.example.com/a.png", "/uploads/games/0123456789abcdef0123456789abcdef.png"):
        assert editor.patch(f'/api/v1/admin/games/{gid}', {"image_url": good}).status_code == 200


@pytest.mark.parametrize("data,ext", [(PNG, "png"), (JPG, "jpg"), (WEBP, "webp")])
def test_staff_can_upload_a_thumbnail_and_it_is_served_safely(game, staff_client, uploads, data, ext):
    editor = staff_client("editor", "content")
    gid = CatalogGame.query.one().id
    r = upload(editor, gid, data, "whatever-name.exe")                 # the filename is ignored: the real bytes decide
    assert r.status_code == 200
    url = r.get_json()["image_url"]
    assert url.startswith("/uploads/games/") and url.endswith("." + ext) and len(os.listdir(uploads / "games")) == 1
    served = editor.c.get(url)
    assert served.status_code == 200 and served.data == data
    assert served.headers["Content-Type"].startswith({"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[ext])
    assert served.headers["X-Content-Type-Options"] == "nosniff" and "default-src 'none'" in served.headers["Content-Security-Policy"]
    assert CatalogGame.query.one().image_url == url


def test_replacing_a_thumbnail_removes_the_old_file(game, staff_client, uploads):
    editor = staff_client("editor", "content")
    gid = CatalogGame.query.one().id
    first = upload(editor, gid, PNG).get_json()["image_url"]
    second = upload(editor, gid, JPG).get_json()["image_url"]
    files = os.listdir(uploads / "games")
    assert first != second and files == [second.rsplit("/", 1)[1]]


@pytest.mark.parametrize("data,name", [
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "evil.svg"),
    (b"<svg onload=alert(1)>", "evil.png"),                            # script dressed up as a png
    (b"GIF89a" + b"0" * 40, "a.gif"), (b"%PDF-1.4" + b"0" * 40, "a.png"), (b"MZ" + b"0" * 40, "a.png"),
    (b"RIFF\x24\x00\x00\x00WAVE" + b"0" * 40, "a.webp"),
])
def test_only_real_png_jpeg_webp_images_are_accepted(game, staff_client, uploads, data, name):
    editor = staff_client("editor", "content")
    r = upload(editor, CatalogGame.query.one().id, data, name)
    assert r.status_code == 400 and not os.path.exists(uploads / "games") or os.listdir(uploads / "games") == []
    assert CatalogGame.query.one().image_url is None


def test_upload_size_missing_file_and_unknown_game(game, staff_client, uploads):
    editor = staff_client("editor", "content")
    gid = CatalogGame.query.one().id
    assert upload(editor, gid, PNG + b"0" * (2 * 1024 * 1024)).status_code == 413
    assert upload(editor, gid, b"").status_code == 400
    assert editor.c.post(f'/api/v1/admin/games/{gid}/thumbnail', data={}, headers={"X-CSRF-Token": editor.token},
                         content_type="multipart/form-data").status_code == 400
    assert upload(editor, 9999, PNG).status_code == 404
    assert CatalogGame.query.one().image_url is None


def test_only_content_staff_can_upload(api, make_player, game, staff_client, uploads):
    gid = CatalogGame.query.one().id
    assert upload(api, gid, PNG).status_code == 401                    # signed out
    make_player(api)
    assert upload(api, gid, PNG).status_code == 403                    # an ordinary player
    assert upload(staff_client("helper", "support"), gid, PNG).status_code == 403
    assert upload(staff_client("editor", "content"), gid, PNG).status_code == 200


def test_uploads_need_the_csrf_token(game, staff_client, uploads):
    editor = staff_client("editor", "content")
    r = editor.c.post(f'/api/v1/admin/games/{CatalogGame.query.one().id}/thumbnail', data={"file": (io.BytesIO(PNG), "a.png")},
                      content_type="multipart/form-data")
    assert r.status_code == 403


@pytest.mark.parametrize("name", ["..%2f..%2fetc%2fpasswd", "x.png", "../app.py", "0123456789ABCDEF0123456789ABCDEF.png",
                                  "0123456789abcdef0123456789abcdef.svg", "0123456789abcdef0123456789abcdef.png.html"])
def test_only_files_we_created_can_be_fetched(app, uploads, name):
    assert app.test_client().get(f'/uploads/games/{name}').status_code == 404
    assert app.test_client().get('/uploads/games/0123456789abcdef0123456789abcdef.png').status_code == 404   # right shape, not there
