"""A missing or mistyped Paydora key must never turn a real site into a fake-payments site."""
from app.services import payments
from tests.test_wallet import deposit, features  # noqa: F401  (fixture + helper)


def test_no_key_and_no_sandbox_means_payments_are_off_not_fake(app, api, make_player, features, monkeypatch):
    features(wallet=True, sandbox=False)
    monkeypatch.setitem(app.config, "PAYDORA_API_KEY", "")
    assert payments.payments_mode() == "disabled" and payments.get_payments() is None
    make_player(api)
    wallet = api.get('/api/v1/wallet').get_json()
    assert wallet["enabled"] is False and wallet["deposit_methods"] == []
    assert deposit(api, 20, "sbx-d-chime").status_code == 501                       # no free fake deposit
    assert api.post('/api/v1/wallet/withdrawals', {"method_id": "sbx-w-cashapp", "amount": 60, "address": "$x", "idempotency_key": "idem-key-00000001"}).status_code == 501


def test_a_key_means_live_even_if_the_sandbox_flag_is_also_on(app, features, monkeypatch):
    features(wallet=True, sandbox=True)
    monkeypatch.setitem(app.config, "PAYDORA_API_KEY", "pk_live_example")
    assert payments.payments_mode() == "live" and payments.get_payments().name == "live"


def test_the_fake_client_only_exists_when_the_sandbox_flag_is_on_and_there_is_no_key(app, features, monkeypatch):
    features(wallet=True, sandbox=True)
    monkeypatch.setitem(app.config, "PAYDORA_API_KEY", "")
    assert payments.payments_mode() == "sandbox" and payments.get_payments().name == "sandbox"
