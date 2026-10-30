"""Referral bonus: when a referred friend's first deposit is credited, the referrer gets $10 in their bonus balance (once)."""
from app import db
from app.models_site import Notification, PaymentOrder, Player, Referral, WalletEntry
from app.services import bonus
from tests.test_wallet import FP, KEY, balance, deposit, features, hook, pay  # noqa: F401  (helpers + fixtures)


def _pair(api, make_player):
    """A referrer, then a friend who signed up with the referrer's code (the api client ends up logged in as the friend)."""
    referrer = make_player(api)
    api.post('/api/v1/auth/logout')
    friend = make_player(api, "friend_one", "friend@example.com", referral_code=referrer["referral_code"])
    return referrer, friend


def _bonus(pid):
    return db.session.get(Player, pid).bonus_cents


def _pay(app, api, amount=25, n=1, delivery="d-1"):
    deposit(api, amount, "m-chime", n)
    order = PaymentOrder.query.order_by(PaymentOrder.id.desc()).first()
    payload = {"depositId": order.provider_deposit_id, "status": "paid", "amount": float(amount), "paidAmount": float(amount)}
    assert hook(app, "deposit.paid", payload, delivery=delivery).status_code == 200
    return order


def test_a_friends_first_deposit_pays_the_referrer_ten_dollars_of_bonus(app, api, make_player, pay):
    referrer, friend = _pair(api, make_player)
    assert Referral.query.one().status == "pending" and _bonus(referrer["id"]) == 0
    _pay(app, api, 25)
    assert _bonus(referrer["id"]) == 1000 and balance(referrer["id"]) == 0       # bonus balance, not withdrawable wallet money
    ref = Referral.query.one()
    assert ref.status == "confirmed" and ref.reward_cents == 1000 and ref.confirmed_at is not None
    assert WalletEntry.query.filter_by(kind="referral_bonus", player_id=referrer["id"], bucket="bonus", amount_cents=1000).count() == 1
    assert Notification.query.filter_by(player_id=referrer["id"], title="Referral bonus").count() == 1
    assert _bonus(friend["id"]) == 0                                              # the friend gets nothing extra from this


def test_it_is_paid_once_even_if_the_friend_deposits_again_or_the_webhook_repeats(app, api, make_player, pay):
    referrer, _ = _pair(api, make_player)
    _pay(app, api, 25, n=1, delivery="d-1")
    _pay(app, api, 25, n=2, delivery="d-2")
    hook(app, "deposit.paid", {"depositId": PaymentOrder.query.first().provider_deposit_id, "status": "paid", "amount": 25.0, "paidAmount": 25.0}, delivery="d-1")
    assert _bonus(referrer["id"]) == 1000
    assert WalletEntry.query.filter_by(kind="referral_bonus").count() == 1


def test_a_signup_alone_pays_nothing(api, make_player, pay):
    referrer, _ = _pair(api, make_player)
    assert _bonus(referrer["id"]) == 0


def test_a_player_who_was_not_referred_pays_nobody(app, api, make_player, pay):
    make_player(api)
    _pay(app, api, 25)
    assert WalletEntry.query.filter_by(kind="referral_bonus").count() == 0


def test_a_deposit_under_the_minimum_does_not_count(app, api, make_player, pay):
    referrer, friend = _pair(api, make_player)
    assert bonus.grant_referral_bonus(friend["id"], 499) == 0
    assert _bonus(referrer["id"]) == 0
    assert bonus.grant_referral_bonus(friend["id"], 500) == 1000
    db.session.commit()
    assert _bonus(referrer["id"]) == 1000


def test_a_referral_staff_rejected_or_a_suspended_referrer_gets_nothing(app, api, make_player, pay):
    referrer, friend = _pair(api, make_player)
    Referral.query.update({"status": "rejected"})
    db.session.commit()
    assert bonus.grant_referral_bonus(friend["id"], 2500) == 0
    Referral.query.update({"status": "pending"})
    db.session.get(Player, referrer["id"]).status = "suspended"
    db.session.commit()
    assert bonus.grant_referral_bonus(friend["id"], 2500) == 0
    assert _bonus(referrer["id"]) == 0


def test_refunding_the_qualifying_deposit_takes_the_bonus_back(app, api, make_player, pay):
    referrer, _ = _pair(api, make_player)
    order = _pay(app, api, 25)
    assert _bonus(referrer["id"]) == 1000
    assert hook(app, "deposit.refunded", {"depositId": order.provider_deposit_id, "refundAmount": 25.0}, delivery="r-1").status_code == 200
    assert _bonus(referrer["id"]) == 0
    assert Referral.query.one().status == "reversed"
    hook(app, "deposit.refunded", {"depositId": order.provider_deposit_id, "refundAmount": 25.0}, delivery="r-2")
    assert _bonus(referrer["id"]) == 0                                            # not taken back twice
    assert _pay(app, api, 25, n=2, delivery="d-3") and _bonus(referrer["id"]) == 0  # and a refunded referral never pays again


def test_the_referral_page_reports_the_reward(app, api, make_player, pay):
    referrer, _ = _pair(api, make_player)
    _pay(app, api, 25)
    api.post('/api/v1/auth/logout')
    api.post('/api/v1/auth/login', {"identifier": referrer["email"], "password": "Sup3rSecret!x"})
    api.refresh()
    body = api.get('/api/v1/referrals/me').get_json()
    assert body["bonus"] == "10" and "$10" in body["rules"] and "first deposit" in body["rules"]
    assert body["items"][0]["status"] == "confirmed" and body["items"][0]["reward"] == "10.00"
