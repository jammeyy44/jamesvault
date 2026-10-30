"""Agent API adapter (Game Vault / Vegas Sweeps): signing, multipart calls, status codes, safe money movement."""
import hashlib
from types import SimpleNamespace

import pytest

from app.services import category6_service as mod
from app.services.category6_service import Category6Service


class Resp:
    def __init__(self, body, status=200):
        self._b, self.status_code = body, status

    def json(self):
        if self._b is None:
            raise ValueError("no json")
        return self._b


@pytest.fixture()
def svc(app, monkeypatch):
    calls = []
    script = {}

    def fake_post(url, files=None, headers=None, timeout=None):
        action = url.rsplit("/", 1)[1]
        fields = {k: v[1] for k, v in files.items()}
        calls.append((action, fields, files))
        r = script.get(action, {"code": 0, "msg": "Success", "data": {}})
        return Resp(r(fields) if callable(r) else r)

    monkeypatch.setattr(mod.requests, "post", fake_post)
    provider = SimpleNamespace(name="Game Vault", base_url="https://agent.example/", username="11", password="s3cret")
    s = Category6Service(provider)
    s.calls, s.script = calls, script
    return s


def test_signature_and_multipart(svc):
    svc.login()
    action, f, files = svc.calls[0]
    assert action == "agentBalance" and f["agent_id"] == "11"
    assert f["token"] == hashlib.md5(f"11:{f['timestamp']}:s3cret".encode()).hexdigest()  # lowercase first
    assert len(f["timestamp"]) == 13
    assert all(v[0] is None for v in files.values())  # multipart parts, not urlencoded


def test_login_reports_status_reason(svc):
    svc.script["agentBalance"] = {"code": 5, "msg": "x", "data": []}
    r = svc.login()
    assert r["error"].startswith("5:") and "whitelisted" in r["error"]


def test_timestamp_unit_falls_back_to_seconds(svc):
    def refuse_ms(fields):
        return {"code": 0, "data": {"agent_balance": "9"}} if len(fields["timestamp"]) == 10 else {"code": 3, "msg": "bad token"}
    svc.script["agentBalance"] = refuse_ms
    assert svc.get_agent_balance()["balance"] == "9" and svc._ms is False


def test_juwa_uses_ten_digit_timestamp_and_lowercase_token(app, monkeypatch):
    sent = []
    monkeypatch.setattr(mod.requests, "post", lambda url, files=None, **kw: (sent.append({k: v[1] for k, v in files.items()}), Resp({"code": 0, "data": {"agent_balance": "1"}}))[1])
    s = Category6Service(SimpleNamespace(name="Juwa 2.0", base_url="https://ht.example", username="5", password="k"))
    s.login()
    f = sent[0]
    assert len(f["timestamp"]) == 10 and f["token"] == hashlib.md5(f"5:{f['timestamp']}:k".encode()).hexdigest() and len(sent) == 1


def test_balance_looks_up_the_player_id_first(svc):
    svc.script["getUserID"] = {"code": 0, "data": {"user_id": "88880212"}}
    svc.script["userBalance"] = {"code": 0, "data": {"user_balance": "60"}}
    assert svc.get_balances("bob")["balance"] == "60"
    assert [c[0] for c in svc.calls] == ["getUserID", "userBalance"] and svc.calls[1][1]["user_id"] == "88880212"


def test_recharge_and_withdraw_send_unique_order_ids(svc):
    svc.script["getUserID"] = {"code": 0, "data": {"user_id": "7"}}
    assert svc.recharge("bob", 20.0)["message"] == "ok"
    assert svc.redeem("bob", 12.5)["message"] == "ok"
    pay = next(c for c in svc.calls if c[0] == "recharge")[1]
    wd = next(c for c in svc.calls if c[0] == "withdraw")[1]
    assert pay["amount"] == "20" and wd["amount"] == "12.50" and pay["order_id"] != wd["order_id"]
    assert pay["order_id"].isdigit()


def test_unknown_player_and_provider_errors_are_clean(svc):
    svc.script["getUserID"] = {"code": 8, "msg": "x"}
    assert "Invalid user ID" in svc.recharge("ghost", 5)["error"]
    svc.script["addUser"] = {"code": 20, "msg": "x"}
    assert "already exists" in svc.add_user("bob", "pw123456")["error"]


def test_network_error_during_money_movement_is_not_swallowed_or_retried(svc, monkeypatch):
    svc.script["getUserID"] = {"code": 0, "data": {"user_id": "7"}}
    n = {"c": 0}
    real = mod.requests.post

    def boom(url, **kw):
        if url.endswith("/recharge"):
            n["c"] += 1
            raise mod.requests.ConnectionError("timeout")
        return real(url, **kw)
    monkeypatch.setattr(mod.requests, "post", boom)
    with pytest.raises(mod.requests.ConnectionError):
        svc.recharge("bob", 5)
    assert n["c"] == 1  # one attempt only: the gateway turns this into 'needs review'
