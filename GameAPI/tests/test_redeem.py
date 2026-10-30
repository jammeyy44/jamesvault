"""Cashout rule table + redeeming winnings from a game into the wallet."""
import pytest

from app import db
from app.models_site import Notification, PaymentOrder, Player, RedeemRequest, WalletEntry
from app.services import cashout_rules as rules, wallet as ledger
from app.services.gateway import GatewayError, SandboxGateway
from tests.test_game_access import features, game  # noqa: F401  (fixtures)
from tests.test_wallet import KEY, deposit, sandbox_wallet  # noqa: F401  (fixtures + helper)

PAYPAL = "sbx-d-paypal"


# ------------------------------------------------------------------ the table, edge by edge (cents)
@pytest.mark.parametrize("deposit,row,lo,hi", [
    (500, 0, 5000, 5000),                       # $5 exactly: $50 / $50
    (501, 1, 5000, 10000), (999, 1, 5000, 10000),   # $5.01 - $9.99: $50 / $100
    (1000, 2, 5000, 12000), (1699, 2, 5000, 20388),  # $10 - $16.99: $50 / x12
    (1700, 3, 5100, 20400), (2599, 3, 7797, 31188),  # $17 - $25.99: x3 / x12
    (2600, 4, 7800, 31200), (3000, 4, 9000, 36000),  # $26 - $30: x3 / x12
    (3001, 5, 9003, 36012),                          # above $30: x3 / x12 ...
    (4166, 5, 12498, 49992), (4167, 5, 12501, 50000),  # ... capped at $500
    (10000, 5, 30000, 50000),
    (20000, 5, 50000, 50000),                        # 3x would be $600 > cap: minimum clamped so the range is never empty
])
def test_every_row_and_edge_of_the_table(deposit, row, lo, hi):
    r = rules.limits(deposit)
    assert (r["row"], r["min_cents"], r["max_cents"]) == (row, lo, hi)
    assert r["min_cents"] <= r["max_cents"]


def test_deposits_under_five_dollars_have_no_row():
    assert rules.limits(499) is None and rules.limits(100) is None and rules.limits(0) is None


def test_outcome_below_within_and_above_the_limits():
    r = rules.limits(1000)                      # $10 deposit: min $50, max $120
    assert rules.outcome(4999, r) == (0, 0)      # below the minimum: nothing can be redeemed
    assert rules.outcome(5000, r) == (5000, 0)
    assert rules.outcome(8000, r) == (8000, 0)
    assert rules.outcome(12000, r) == (12000, 0)
    assert rules.outcome(20000, r) == (12000, 8000)   # above the maximum: excess is voided


def test_table_text_matches_the_rule_sheet():
    assert [(t["deposit"], t["min"], t["max"]) for t in rules.TABLE] == [
        ("$5", "$50", "$50"), ("$5 - $9", "$50", "$100"), ("$10 - $16", "$50", "x12"),
        ("$17 - $25", "x3", "x12"), ("$26 - $30", "x3", "x12"), ("$30+", "x3", "x12 (max $500)")]
    assert "voided" in rules.NOTE


# ------------------------------------------------------------------ helpers
def setup_player(api, make_player, amount=10, name="player_one", email="p1@example.com", n=1):
    p = make_player(api, username=name, email=email)
    if amount:
        assert deposit(api, amount, PAYPAL, n).status_code == 201
    return p


def with_access(api, slug="game-vault"):
    assert api.post(f'/api/v1/games/{slug}/access').status_code == 201


def win(api, amount, slug="game-vault"):
    assert api.post(f'/api/v1/games/{slug}/sandbox/win', {"amount": str(amount)}).status_code == 201


def preview(api, slug="game-vault"):
    return api.get(f'/api/v1/games/{slug}/redeem').get_json()


def do_redeem(api, n=1, confirm=False, slug="game-vault"):
    return api.post(f'/api/v1/games/{slug}/redeem', {"idempotency_key": KEY(n), "confirm_void": confirm})


def wallet_cents(pid):
    return db.session.get(Player, pid).wallet_cents


def game_balance(api, slug="game-vault"):
    return api.get(f'/api/v1/games/{slug}/balance').get_json()["balance"]


# ------------------------------------------------------------------ eligibility
def test_requires_login_and_a_game_account(api, make_player, game, sandbox_wallet):
    assert api.get('/api/v1/games/game-vault/redeem').status_code == 401
    make_player(api)
    assert api.get('/api/v1/games/game-vault/redeem').status_code == 404
    assert do_redeem(api).status_code == 404


def test_no_deposit_means_no_redeem(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, amount=0)
    with_access(api)
    pre = preview(api)
    assert pre["can_redeem"] is False and "deposit of $5" in pre["reason"] and pre["latest_deposit"] is None
    r = do_redeem(api)
    assert r.status_code == 409 and r.get_json()["code"] == "not_redeemable" and RedeemRequest.query.count() == 0


def test_deposits_under_five_are_refused_so_every_deposit_has_a_row(api, make_player, sandbox_wallet):
    make_player(api)
    assert deposit(api, 4.99, PAYPAL, 1).status_code == 400
    assert deposit(api, 5, PAYPAL, 2).status_code == 201
    assert api.get('/api/v1/wallet').get_json()["deposit"]["min"] == "5"


def test_below_the_minimum_is_refused_with_the_numbers(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 10)             # min $50
    with_access(api)
    win(api, 30)
    pre = preview(api)
    assert pre["can_redeem"] is False and "$50.00" in pre["reason"] and "$30.00" in pre["reason"]
    assert pre["rule"] == {"row": 2, "deposit": "10.00", "min": "50.00", "max": "120.00"}
    assert do_redeem(api).status_code == 409 and wallet_cents(p["id"]) == 1000 and game_balance(api) == "30.00"


# ------------------------------------------------------------------ redeeming
def test_redeem_within_the_range_moves_the_winnings_to_the_wallet(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 10)
    with_access(api)
    win(api, 80)
    pre = preview(api)
    assert pre["can_redeem"] and pre["payout"] == "80.00" and pre["voided"] == "0.00" and pre["needs_confirm"] is False
    r = do_redeem(api)
    body = r.get_json()
    assert r.status_code == 201 and body["status"] == "completed" and body["payout"] == "80.00" and body["voided"] == "0.00"
    assert wallet_cents(p["id"]) == 1000 + 8000
    assert game_balance(api) == "0.00"                              # the whole balance left the game
    e = WalletEntry.query.filter_by(kind="redeem").one()
    assert (e.bucket, e.amount_cents) == ("wallet", 8000)
    assert Notification.query.filter_by(player_id=p["id"], title="Winnings redeemed").count() == 1


def test_amount_above_the_maximum_is_voided_and_needs_confirmation(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 10)             # max $120
    with_access(api)
    win(api, 200)
    pre = preview(api)
    assert pre["payout"] == "120.00" and pre["voided"] == "80.00" and pre["needs_confirm"] is True
    r = do_redeem(api)                                              # no confirmation: nothing happens
    assert r.status_code == 409 and r.get_json()["code"] == "confirm_void" and r.get_json()["voided"] == "80.00"
    assert wallet_cents(p["id"]) == 1000 and game_balance(api) == "200.00" and RedeemRequest.query.count() == 0
    done = do_redeem(api, confirm=True).get_json()
    assert done["status"] == "completed" and done["payout"] == "120.00" and done["voided"] == "80.00"
    assert wallet_cents(p["id"]) == 1000 + 12000                    # only the payout is credited, never the voided part
    assert game_balance(api) == "0.00"
    assert RedeemRequest.query.one().void_cents == 8000
    assert "voided" in Notification.query.filter_by(title="Winnings redeemed").one().body


def test_a_confirm_flag_that_is_not_literally_true_does_not_count(api, make_player, game, sandbox_wallet):
    setup_player(api, make_player, 10)
    with_access(api)
    win(api, 200)
    for flag in ("true", 1, "yes", None):
        assert do_redeem(api, 5, confirm=flag).status_code == 409
    assert RedeemRequest.query.count() == 0


def test_exactly_five_dollar_deposit_is_fifty_fifty(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 5)
    with_access(api)
    win(api, 49.99)
    assert preview(api)["can_redeem"] is False
    win(api, 50.01)                                                 # balance now exactly 100 -> payout 50, void 50
    pre = preview(api)
    assert (pre["payout"], pre["voided"]) == ("50.00", "50.00")
    assert do_redeem(api, confirm=True).get_json()["payout"] == "50.00" and wallet_cents(p["id"]) == 500 + 5000


def test_replaying_a_redeem_never_pays_twice(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 10)
    with_access(api)
    win(api, 80)
    first = do_redeem(api, 1).get_json()
    again = do_redeem(api, 1)
    assert again.status_code == 200 and again.get_json()["id"] == first["id"]
    assert wallet_cents(p["id"]) == 9000 and RedeemRequest.query.count() == 1


def test_one_redeem_per_deposit_then_a_new_deposit_unlocks_the_next(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 10)
    with_access(api)
    win(api, 80)
    assert do_redeem(api, 1).status_code == 201
    win(api, 90)
    pre = preview(api)
    assert pre["can_redeem"] is False and "already redeemed" in pre["reason"]
    assert do_redeem(api, 2).status_code == 409 and wallet_cents(p["id"]) == 9000
    assert deposit(api, 20, PAYPAL, 2).status_code == 201           # a new deposit sets new limits ($20: min $60)
    assert preview(api)["rule"]["min"] == "60.00"
    assert do_redeem(api, 3).status_code == 201 and wallet_cents(p["id"]) == 9000 + 2000 + 9000


def test_the_most_recent_deposit_decides_the_limits(api, make_player, game, sandbox_wallet):
    setup_player(api, make_player, 5)
    deposit(api, 20, PAYPAL, 2)
    with_access(api)
    assert preview(api)["rule"] == {"row": 3, "deposit": "20.00", "min": "60.00", "max": "240.00"}   # not the $5 row
    # and a later SMALLER deposit replaces it
    deposit(api, 5, PAYPAL, 3)
    assert preview(api)["rule"]["row"] == 0 and preview(api)["rule"]["min"] == "50.00"


def test_a_refunded_latest_deposit_falls_back_to_the_one_before(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 10)
    with_access(api)
    deposit(api, 20, PAYPAL, 2)
    order = PaymentOrder.query.order_by(PaymentOrder.id.desc()).first()
    assert preview(api)["rule"]["deposit"] == "20.00"
    ledger.debit(p["id"], 2000, "refund", "payment_order", order.id, allow_negative=True)
    db.session.commit()
    assert preview(api)["rule"]["deposit"] == "10.00"


def test_bonus_and_other_credits_are_not_deposits(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 0)
    ledger.credit(p["id"], 5000, "adjustment", "admin", "a")
    ledger.credit(p["id"], 5000, "deposit_bonus", "payment_order", "9", bucket="bonus")
    ledger.credit(p["id"], 5000, "redeem", "redeem_request", "7")
    db.session.commit()
    with_access(api)
    assert preview(api)["latest_deposit"] is None and do_redeem(api).status_code == 409


def test_sandbox_winnings_route_is_sandbox_only(api, make_player, game, sandbox_wallet, features):
    setup_player(api, make_player, 10)
    with_access(api)
    features(sandbox=False)
    assert api.post('/api/v1/games/game-vault/sandbox/win', {"amount": "50"}).status_code == 404


def test_two_requests_cannot_both_redeem_the_same_deposit(api, make_player, game, sandbox_wallet):
    p = setup_player(api, make_player, 10)
    with_access(api)
    win(api, 80)
    dep = rules.latest_deposit(p["id"])
    acct_id = db.session.query(__import__("app.models_site", fromlist=["GameAccount"]).GameAccount.id).scalar()
    db.session.add(RedeemRequest(player_id=p["id"], game_account_id=acct_id, deposit_lock_id=dep.id, deposit_cents=1000, min_cents=5000,
                                 max_cents=12000, balance_cents=8000, payout_cents=8000, status="processing", idempotency_key="other-key-0001"))
    db.session.commit()
    r = do_redeem(api)
    assert r.status_code == 409 and wallet_cents(p["id"]) == 1000 and game_balance(api) == "80.00"


# ------------------------------------------------------------------ provider problems
class RefusingGateway(SandboxGateway):
    def redeem(self, account, amount):
        raise GatewayError("The game provider could not complete that request. Please try again later.")


class UnclearGateway(SandboxGateway):
    def redeem(self, account, amount):
        raise TimeoutError("read timed out")


def test_a_refused_redeem_changes_nothing_and_can_be_retried(api, make_player, game, sandbox_wallet, monkeypatch):
    p = setup_player(api, make_player, 10)
    with_access(api)
    win(api, 80)
    monkeypatch.setattr("app.routes.site.redeem.get_gateway", lambda: RefusingGateway())
    r = do_redeem(api, 1).get_json()
    assert r["status"] == "failed" and wallet_cents(p["id"]) == 1000 and game_balance(api) == "80.00"
    assert RedeemRequest.query.one().deposit_lock_id is None          # the deposit is released
    monkeypatch.undo()
    assert do_redeem(api, 2).get_json()["status"] == "completed" and wallet_cents(p["id"]) == 9000


def test_an_unclear_outcome_credits_nothing_and_needs_a_person(api, make_player, game, sandbox_wallet, monkeypatch, staff_client):
    p = setup_player(api, make_player, 10)
    with_access(api)
    win(api, 80)
    monkeypatch.setattr("app.routes.site.redeem.get_gateway", lambda: UnclearGateway())
    r = do_redeem(api, 1).get_json()
    assert r["status"] == "needs_review" and wallet_cents(p["id"]) == 1000
    monkeypatch.undo()
    assert do_redeem(api, 2).status_code == 409                       # still locked: cannot redeem again meanwhile

    helper = staff_client("helper", "support")
    assert helper.patch(f'/api/v1/admin/redeems/{r["id"]}', {"action": "resolve_completed"}).status_code == 403
    root = staff_client("root", "superadmin")
    listed = root.get('/api/v1/admin/redeems?status=needs_review').get_json()["items"]
    assert [i["id"] for i in listed] == [r["id"]] and listed[0]["payout"] == "80.00"
    assert root.patch(f'/api/v1/admin/redeems/{r["id"]}', {"action": "resolve_completed"}).get_json()["status"] == "completed"
    assert root.patch(f'/api/v1/admin/redeems/{r["id"]}', {"action": "resolve_completed"}).status_code == 409
    assert wallet_cents(p["id"]) == 9000                              # credited exactly once


def test_staff_can_release_an_unclear_redeem_that_did_not_happen(api, make_player, game, sandbox_wallet, monkeypatch, staff_client):
    p = setup_player(api, make_player, 10)
    with_access(api)
    win(api, 80)
    monkeypatch.setattr("app.routes.site.redeem.get_gateway", lambda: UnclearGateway())
    rid = do_redeem(api, 1).get_json()["id"]
    monkeypatch.undo()
    root = staff_client("root", "superadmin")
    assert root.patch(f'/api/v1/admin/redeems/{rid}', {"action": "resolve_failed"}).status_code == 200
    assert wallet_cents(p["id"]) == 1000 and RedeemRequest.query.one().deposit_lock_id is None
    assert do_redeem(api, 2).get_json()["status"] == "completed" and wallet_cents(p["id"]) == 9000


# ------------------------------------------------------------------ wallet display
def test_wallet_payload_carries_the_rule_and_current_limits(api, make_player, sandbox_wallet):
    make_player(api)
    w = api.get('/api/v1/wallet').get_json()["cashout_rule"]
    assert w["latest_deposit"] is None and w["min"] is None and len(w["table"]) == 6 and "voided" in w["note"]
    deposit(api, 20, PAYPAL, 1)
    w = api.get('/api/v1/wallet').get_json()["cashout_rule"]
    assert (w["latest_deposit"], w["row"], w["min"], w["max"]) == ("20.00", 3, "60.00", "240.00")


def test_history_lists_redeems_with_the_voided_amount(api, make_player, game, sandbox_wallet):
    setup_player(api, make_player, 10)
    with_access(api)
    win(api, 200)
    do_redeem(api, 1, confirm=True)
    item = next(o for o in api.get('/api/v1/wallet/history').get_json()["orders"] if o["type"] == "redeem")
    assert (item["amount"], item["voided"], item["status"]) == ("120.00", "80.00", "completed")


# ------------------------------------------------------------------ admin slug validation
@pytest.mark.parametrize("slug", ["Game Vault", "game vault", "game/vault", "GAME", "-x", "x-", "a--b", "", "x" * 81, "../etc"])
def test_game_slugs_must_be_url_safe(staff_client, slug):
    editor = staff_client("editor", "content")
    assert editor.post('/api/v1/admin/games', {"slug": slug, "name": "X"}).status_code == 400


@pytest.mark.parametrize("slug", ["game-vault", "fire-kirin", "x1", "a-b-c-2"])
def test_valid_game_slugs_are_accepted(staff_client, slug):
    editor = staff_client("editor", "content")
    assert editor.post('/api/v1/admin/games', {"slug": slug, "name": "X"}).status_code == 201
