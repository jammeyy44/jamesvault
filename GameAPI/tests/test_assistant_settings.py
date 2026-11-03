"""Admin page for the voice assistant's AI key: write-only, encrypted at rest, superadmin only."""
from app import db
from app.models_site import AppSetting, AuditLog
from app.services import assistant_settings as cfg

KEY = "nvapi-" + "A1b2C3d4E5f6G7h8I9j0" * 3


def test_only_a_superadmin_can_see_or_change_it(api, make_player, staff_client, admin_api):
    make_player(api)
    for method in ("get", "put"):
        r = getattr(api, method)('/api/v1/admin/assistant-settings') if method == "get" else api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia"})
        assert r.status_code == 403
    support = staff_client("helper", "support")
    assert support.get('/api/v1/admin/assistant-settings').status_code == 403
    assert admin_api.get('/api/v1/admin/assistant-settings').status_code == 200


def test_key_is_saved_encrypted_and_never_returned(app, admin_api, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert admin_api.get('/api/v1/admin/assistant-settings').get_json()["providers"]["nvidia"]["key_set"] is False
    r = admin_api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia", "model": "nvidia/nemotron-3.5-lightning-30b-a3b", "api_key": KEY})
    assert r.status_code == 200
    view = r.get_json()["providers"]["nvidia"]
    assert view["key_set"] is True and view["key_hint"] == KEY[-4:].join(["…", ""]) and view["source"] == "admin"
    assert KEY not in r.get_data(as_text=True) and KEY not in admin_api.get('/api/v1/admin/assistant-settings').get_data(as_text=True)
    raw = db.session.execute(db.text("select value from app_settings where key = 'assistant.key.nvidia'")).scalar()
    assert raw.startswith("enc:") and KEY not in raw                     # encrypted at rest
    assert cfg.api_key("nvidia") == KEY                                   # but the server can use it
    logged = " ".join(str(l.detail) for l in AuditLog.query.filter(AuditLog.action.like("assistant.%")).all())
    assert KEY not in logged                                              # and it never reaches the audit log


def test_bad_pastes_are_refused(admin_api):
    assert admin_api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia", "api_key": "sk-ant-" + "x" * 40}).status_code == 400   # wrong provider's key
    assert admin_api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia", "api_key": "nvapi- has spaces in it " + "x" * 20}).status_code == 400
    assert admin_api.put('/api/v1/admin/assistant-settings', {"provider": "bogus"}).status_code == 400
    assert admin_api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia", "model": "two words"}).status_code == 400


def test_saving_without_a_key_keeps_the_old_one_and_it_can_be_removed(admin_api):
    admin_api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia", "api_key": KEY})
    admin_api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia", "model": "nvidia/other-model"})
    assert cfg.api_key("nvidia") == KEY and cfg.model("nvidia") == "nvidia/other-model"
    r = admin_api.delete('/api/v1/admin/assistant-settings/key?provider=nvidia')
    assert r.status_code == 200 and r.get_json()["providers"]["nvidia"]["key_set"] is False


def test_connection_test_reports_without_leaking_the_key(admin_api, monkeypatch):
    admin_api.put('/api/v1/admin/assistant-settings', {"provider": "nvidia", "api_key": KEY})
    seen = {}

    class Resp:
        def __init__(self, code): self.status_code = code

    def fake_post(url, **kw):
        seen["auth"] = kw["headers"]["Authorization"]
        seen["body"] = kw["json"]
        return Resp(200)
    monkeypatch.setattr("app.services.assistant_settings.requests.post", fake_post)
    r = admin_api.post('/api/v1/admin/assistant-settings/test', {"provider": "nvidia"}).get_json()
    assert r["ok"] is True and KEY not in str(r)
    assert seen["auth"] == f"Bearer {KEY}" and seen["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    monkeypatch.setattr("app.services.assistant_settings.requests.post", lambda url, **kw: Resp(401))
    bad = admin_api.post('/api/v1/admin/assistant-settings/test', {"provider": "nvidia"}).get_json()
    assert bad["ok"] is False and "rejected" in bad["message"] and KEY not in str(bad)
