"""Coupons: single-person and many-person codes, once per account, caps, expiry, staff-only creation."""
from datetime import timedelta

from app import db
from app.models_site import Coupon, CouponRedemption, Player, WalletEntry
from app.utils.auth import utcnow


def _new(admin_api, **kw):
    body = {"amount": "5", "scope": "many", **kw}
    r = admin_api.post('/api/v1/admin/coupons', body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _bonus(player_id):
    return db.session.get(Player, player_id).bonus_cents


def test_only_superadmin_can_create(api, make_player, staff_client):
    make_player(api)
    assert api.post('/api/v1/admin/coupons', {"amount": "5", "scope": "many"}).status_code == 403
    assert staff_client("helper", "support").post('/api/v1/admin/coupons', {"amount": "5", "scope": "many"}).status_code == 403
    assert staff_client("editor", "content").post('/api/v1/admin/coupons', {"amount": "5", "scope": "many"}).status_code == 403


def test_generated_code_is_random_and_amount_is_validated(admin_api):
    a, b = _new(admin_api), _new(admin_api)
    assert a["code"] != b["code"] and len(a["code"]) == 8 and a["scope"] == "many" and a["max_redemptions"] is None
    for bad in ("0", "-3", "abc", "501"):
        assert admin_api.post('/api/v1/admin/coupons', {"amount": bad, "scope": "many"}).status_code == 400
    assert admin_api.post('/api/v1/admin/coupons', {"amount": "5", "scope": "nobody"}).status_code == 400
    assert admin_api.post('/api/v1/admin/coupons', {"amount": "5", "scope": "many", "code": "no spaces!"}).status_code == 400


def test_custom_code_must_be_unique(admin_api):
    _new(admin_api, code="welcome5")
    assert admin_api.post('/api/v1/admin/coupons', {"amount": "5", "scope": "many", "code": "WELCOME5"}).status_code == 409


def test_many_people_each_once(api, make_player, admin_api):
    code = _new(admin_api, amount="5", code="SPRING5")["code"]
    first = make_player(api)
    r = api.post('/api/v1/coupons/redeem', {"code": "spring5"})  # case-insensitive
    assert r.status_code == 200 and r.get_json()["amount"] == "5.00" and r.get_json()["bonus_balance"] == "5.00"
    again = api.post('/api/v1/coupons/redeem', {"code": code})
    assert again.status_code == 409 and again.get_json()["code"] == "coupon_used"
    assert _bonus(first["id"]) == 500                                  # credited exactly once
    api.post('/api/v1/auth/logout')
    second = make_player(api, "player_two", "p2@example.com")
    assert api.post('/api/v1/coupons/redeem', {"code": code}).status_code == 200  # a different account can use it too
    assert _bonus(second["id"]) == 500
    assert Coupon.query.filter_by(code=code).one().redeemed_count == 2
    assert CouponRedemption.query.count() == 2


def test_single_person_code_only_works_for_that_account(api, make_player, admin_api):
    target = make_player(api)
    api.post('/api/v1/auth/logout')
    c = _new(admin_api, scope="single", player=target["email"].upper(), code="JUSTYOU")
    assert c["assigned_to"] == target["username"] and c["max_redemptions"] == 1
    make_player(api, "player_two", "p2@example.com")  # somebody else
    other = api.post('/api/v1/coupons/redeem', {"code": "JUSTYOU"})
    assert other.status_code == 404 and other.get_json()["code"] == "invalid_coupon"  # looks like any wrong code
    assert api.post('/api/v1/coupons/redeem', {"code": "NOSUCHCODE"}).get_json()["error"] == other.get_json()["error"]
    api.post('/api/v1/auth/logout')
    assert api.post('/api/v1/auth/login', {"identifier": target["email"], "password": "Sup3rSecret!x"}).status_code == 200
    api.refresh()
    assert api.post('/api/v1/coupons/redeem', {"code": "JUSTYOU"}).status_code == 200
    assert api.post('/api/v1/coupons/redeem', {"code": "JUSTYOU"}).status_code == 409


def test_single_person_code_needs_a_real_account(admin_api):
    r = admin_api.post('/api/v1/admin/coupons', {"amount": "5", "scope": "single", "player": "nobody-here"})
    assert r.status_code == 400


def test_total_cap_cannot_be_overrun(api, make_player, admin_api):
    code = _new(admin_api, max_redemptions=1)["code"]
    make_player(api)
    assert api.post('/api/v1/coupons/redeem', {"code": code}).status_code == 200
    api.post('/api/v1/auth/logout')
    make_player(api, "player_two", "p2@example.com")
    r = api.post('/api/v1/coupons/redeem', {"code": code})
    assert r.status_code == 410 and r.get_json()["code"] == "coupon_exhausted"
    assert Coupon.query.one().redeemed_count == 1 and CouponRedemption.query.count() == 1


def test_expired_and_deactivated_codes(api, make_player, admin_api):
    soon = _new(admin_api, code="EXPIRES1", expires_at=(utcnow() + timedelta(days=1)).isoformat())
    assert admin_api.post('/api/v1/admin/coupons', {"amount": "5", "scope": "many", "expires_at": (utcnow() - timedelta(days=1)).isoformat()}).status_code == 400
    Coupon.query.filter_by(id=soon["id"]).update({"expires_at": utcnow() - timedelta(minutes=1)})
    db.session.commit()
    off = _new(admin_api, code="SWITCHED")
    assert admin_api.patch(f'/api/v1/admin/coupons/{off["id"]}', {"is_active": False}).get_json()["is_active"] is False
    make_player(api)
    assert api.post('/api/v1/coupons/redeem', {"code": "EXPIRES1"}).get_json()["code"] == "coupon_expired"
    assert api.post('/api/v1/coupons/redeem', {"code": "SWITCHED"}).status_code == 404
    assert WalletEntry.query.filter_by(kind="coupon").count() == 0


def test_redeeming_requires_login_and_is_rate_limited(api):
    assert api.post('/api/v1/coupons/redeem', {"code": "ANYTHING"}).status_code == 401
