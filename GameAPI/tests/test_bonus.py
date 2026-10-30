"""Bonus Zone: diamond tasks, weekly streak and the Lucky Shop boxes."""
import hashlib
from datetime import timedelta

import pytest

from app import db
from app.models_site import (
    BonusBox, BonusTask, DiamondEntry, PasswordResetToken, Player, PlayerReward, Referral, TaskClaim,
)
from app.services import bonus, wallet as ledger
from app.utils.auth import utcnow
from tests.test_game_access import features  # noqa: F401  (fixture)


@pytest.fixture()
def zone(app):
    bonus.ensure_defaults()
    db.session.commit()


def diamonds(pid):
    return db.session.get(Player, pid).diamonds


def give(pid, n):
    bonus.credit_diamonds(pid, n, 'adjustment', 'test', f"give-{pid}-{n}-{utcnow().timestamp()}")
    db.session.commit()


def get(api):
    return api.get('/api/v1/bonus').get_json()


def task(api, key):
    return next(t for t in get(api)["tasks"] + [get(api)["streak"]["task"]] if t and t["key"] == key)


def claim(api, key):
    return api.post(f'/api/v1/bonus/tasks/{key}/claim')


def open_box(api, box_id, n=1):
    return api.post(f'/api/v1/bonus/boxes/{box_id}/open', {"idempotency_key": f"open-key-{n:08d}"})


# ------------------------------------------------------------------ defaults + listing
def test_requires_login(api, zone):
    assert api.get('/api/v1/bonus').status_code == 401
    assert claim(api, 'daily_login').status_code == 401
    assert api.post('/api/v1/bonus/boxes/1/open', {"idempotency_key": "open-key-00000001"}).status_code == 401


def test_default_boxes_hold_exactly_the_specified_rewards(api, make_player, zone):
    make_player(api)
    boxes = get(api)["boxes"]
    assert [b["prize_label"] for b in boxes] == ["$2 Free Play", "$3 Free Play", "$4 Free Play", "20% Deposit Bonus", "$5 Bonus"]
    assert [b["cost_diamonds"] for b in boxes] == sorted(b["cost_diamonds"] for b in boxes)
    assert all(b["affordable"] is False for b in boxes)


def test_ensure_defaults_is_idempotent_and_never_overwrites_edits(zone):
    t = BonusTask.query.filter_by(key="daily_login").one()
    t.reward_diamonds = 9
    db.session.commit()
    n_tasks, n_boxes = BonusTask.query.count(), BonusBox.query.count()
    bonus.ensure_defaults()
    db.session.commit()
    assert (BonusTask.query.count(), BonusBox.query.count()) == (n_tasks, n_boxes)
    assert BonusTask.query.filter_by(key="daily_login").one().reward_diamonds == 9


def test_week_has_seven_days_and_marks_today(api, make_player, zone):
    make_player(api)
    week = get(api)["streak"]["week"]
    assert [d["label"] for d in week] == ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    assert sum(d["today"] for d in week) == 1


# ------------------------------------------------------------------ tasks
def test_daily_login_claims_once_per_day(api, make_player, zone):
    p = make_player(api)
    r = claim(api, 'daily_login')
    assert r.status_code == 201 and r.get_json()["diamonds_awarded"] == 1 and diamonds(p["id"]) == 1
    assert claim(api, 'daily_login').status_code == 409
    assert diamonds(p["id"]) == 1 and TaskClaim.query.count() == 1
    assert task(api, 'daily_login')["state"] == "claimed"
    assert any(d["claimed"] and d["today"] for d in get(api)["streak"]["week"])


def test_a_new_day_can_be_claimed_again(api, make_player, zone):
    p = make_player(api)
    claim(api, 'daily_login')
    # pretend that claim happened yesterday
    TaskClaim.query.update({"claim_key": f"daily_login:{p['id']}:{(utcnow().date() - timedelta(days=1)).isoformat()}"})
    db.session.commit()
    assert claim(api, 'daily_login').status_code == 201 and diamonds(p["id"]) == 2


def test_unknown_inactive_and_incomplete_tasks_cannot_be_claimed(api, make_player, zone):
    make_player(api)
    assert claim(api, 'nope').status_code == 404
    BonusTask.query.filter_by(key="daily_login").update({"is_active": False})
    db.session.commit()
    assert claim(api, 'daily_login').status_code == 404
    assert "daily_login" not in {t["key"] for t in get(api)["tasks"]}
    r = claim(api, 'first_deposit')
    assert r.status_code == 409 and "deposits" in r.get_json()["error"].lower()


def test_email_task_needs_a_real_verification_link(api, make_player, zone, monkeypatch):
    p = make_player(api)
    sent = {}
    monkeypatch.setattr("app.routes.site.player.send_email", lambda to, subject, body: sent.update(body=body))
    assert claim(api, 'verify_email').status_code == 409  # not verified: no diamonds for just clicking
    assert api.post('/api/v1/auth/verify-email/request').status_code == 200
    raw = sent["body"].split("token=")[1].split()[0]
    assert api.post('/api/v1/auth/verify-email', {"token": "garbage"}).status_code == 400
    assert api.post('/api/v1/auth/verify-email', {"token": raw}).status_code == 200
    assert api.post('/api/v1/auth/verify-email', {"token": raw}).status_code == 400  # single use
    assert db.session.get(Player, p["id"]).email_verified is True
    assert claim(api, 'verify_email').status_code == 201 and diamonds(p["id"]) == 2
    assert claim(api, 'verify_email').status_code == 409


def test_tokens_are_not_interchangeable_between_reset_and_verification(api, make_player, zone):
    p = make_player(api)

    def put(purpose, raw):
        db.session.add(PasswordResetToken(player_id=p["id"], purpose=purpose, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                                          expires_at=utcnow() + timedelta(hours=1)))
        db.session.commit()
    put('reset', 'reset-token-aaaaaaaaaaaaaaaaaaaaaa')
    put('verify_email', 'verify-token-bbbbbbbbbbbbbbbbbbbb')
    assert api.post('/api/v1/auth/verify-email', {"token": "reset-token-aaaaaaaaaaaaaaaaaaaaaa"}).status_code == 400
    assert api.post('/api/v1/auth/reset', {"token": "verify-token-bbbbbbbbbbbbbbbbbbbb", "password": "BrandNewPass99"}).status_code == 400


def test_expired_verification_link(api, make_player, zone):
    p = make_player(api)
    db.session.add(PasswordResetToken(player_id=p["id"], purpose='verify_email', token_hash=hashlib.sha256(b"old-token-ccccccccccccccc").hexdigest(),
                                      expires_at=utcnow() - timedelta(minutes=1)))
    db.session.commit()
    assert api.post('/api/v1/auth/verify-email', {"token": "old-token-ccccccccccccccc"}).status_code == 400


def _login_claims(pid, days):
    for d in days:
        db.session.add(TaskClaim(player_id=pid, task_key="daily_login", claim_key=f"daily_login:{pid}:{d.isoformat()}", diamonds=1))
    db.session.commit()


def test_weekly_streak_needs_all_seven_days_and_pays_once_per_week(api, make_player, zone):
    p = make_player(api)
    days = bonus.week_days(utcnow().date())
    _login_claims(p["id"], days[:6])
    t = task(api, 'weekly_streak')
    assert t["state"] == "locked" and t["progress"] == {"done": 6, "total": 7}
    assert claim(api, 'weekly_streak').status_code == 409
    _login_claims(p["id"], days[6:])
    assert task(api, 'weekly_streak')["state"] == "claimable"
    assert claim(api, 'weekly_streak').status_code == 201 and diamonds(p["id"]) == 5
    assert claim(api, 'weekly_streak').status_code == 409 and diamonds(p["id"]) == 5


def test_deposit_tasks_use_the_wallet_ledger_and_are_locked_without_a_wallet(api, make_player, zone, features):
    p = make_player(api)
    assert task(api, 'daily_deposit')["state"] == "locked" and "enabled" in task(api, 'daily_deposit')["reason"]
    features(wallet=True)
    ledger.credit(p["id"], 1000, 'deposit', 'payment_order', 1)  # $10: below the $20 threshold
    db.session.commit()
    t = task(api, 'daily_deposit')
    assert t["state"] == "locked" and t["progress"] == {"done": 10, "total": 20}
    assert claim(api, 'daily_deposit').status_code == 409
    assert task(api, 'first_deposit')["state"] == "claimable"
    ledger.credit(p["id"], 1500, 'deposit', 'payment_order', 2)  # $25 total >= $20
    db.session.commit()
    assert claim(api, 'daily_deposit').status_code == 201 and claim(api, 'daily_deposit').status_code == 409
    assert claim(api, 'first_deposit').status_code == 201
    assert diamonds(p["id"]) == 2 + 5


def test_non_deposit_wallet_movements_do_not_count_as_deposits(api, make_player, zone, features):
    p = make_player(api)
    features(wallet=True)
    ledger.credit(p["id"], 5000, 'adjustment', 'admin', 'x')
    ledger.credit(p["id"], 5000, 'withdrawal_refund', 'withdrawal', 'y')
    db.session.commit()
    assert task(api, 'daily_deposit')["state"] == "locked" and task(api, 'first_deposit')["state"] == "locked"


def test_refer_friend_pays_per_confirmed_referral_only(app, api, make_player, zone):
    from tests.conftest import Api
    me = make_player(api)
    friends = []
    for i in range(2):
        c = Api(app.test_client())
        friends.append(make_player(c, username=f"friend_{i}", email=f"f{i}@example.com", referral_code=me["referral_code"]))
    assert task(api, 'refer_friend')["state"] == "locked"  # still pending: staff haven't confirmed
    Referral.query.filter_by(referred_id=friends[0]["id"]).update({"status": "confirmed"})
    db.session.commit()
    assert task(api, 'refer_friend')["state"] == "claimable" and task(api, 'refer_friend')["available"] == 1
    assert claim(api, 'refer_friend').status_code == 201 and diamonds(me["id"]) == 3
    assert claim(api, 'refer_friend').status_code == 409  # that referral is used up
    Referral.query.filter_by(referred_id=friends[1]["id"]).update({"status": "confirmed"})
    db.session.commit()
    assert claim(api, 'refer_friend').status_code == 201 and diamonds(me["id"]) == 6


def test_tournaments_are_gone_from_the_bonus_zone(api, make_player, zone):
    make_player(api)
    assert "join_tournament" not in {t["key"] for t in get(api)["tasks"]}
    assert BonusTask.query.filter_by(key="join_tournament").count() == 0
    assert claim(api, 'join_tournament').status_code == 404


def test_retired_task_rows_are_removed_from_existing_databases(zone):
    db.session.add(BonusTask(key="join_tournament", title="Join a tournament", reward_diamonds=2, group="general", kind="one_time"))
    db.session.commit()
    bonus.ensure_defaults()
    db.session.commit()
    assert BonusTask.query.filter_by(key="join_tournament").count() == 0


# ------------------------------------------------------------------ Lucky Shop
def _box(label):
    return next(b for b in BonusBox.query.all() if b.prize_label == label)


def test_opening_needs_diamonds_and_spends_nothing_when_short(api, make_player, zone):
    p = make_player(api)
    box = _box("$2 Free Play")
    r = open_box(api, box.id)
    assert r.status_code == 402 and r.get_json()["code"] == "insufficient_diamonds" and "5 more" in r.get_json()["error"]
    assert PlayerReward.query.count() == 0 and DiamondEntry.query.count() == 0
    give(p["id"], 4)
    assert open_box(api, box.id, 2).status_code == 402 and diamonds(p["id"]) == 4


def test_opening_spends_diamonds_and_grants_the_fixed_reward(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 7)
    box = _box("$2 Free Play")
    r = open_box(api, box.id)
    body = r.get_json()
    assert r.status_code == 201 and body["reward"]["label"] == "$2 Free Play" and body["reward"]["value_cents"] == 200
    assert body["diamonds"] == 2 and diamonds(p["id"]) == 2
    assert PlayerReward.query.one().status == "applied"  # applied instantly, no staff step
    assert get(api)["rewards"][0]["label"] == "$2 Free Play"


@pytest.mark.parametrize("label,kind,cents,percent", [
    ("$2 Free Play", "freeplay", 200, None), ("$3 Free Play", "freeplay", 300, None), ("$4 Free Play", "freeplay", 400, None),
    ("20% Deposit Bonus", "deposit_bonus_percent", None, 20), ("$5 Bonus", "bonus_cash", 500, None),
])
def test_every_box_delivers_what_it_says(api, make_player, zone, label, kind, cents, percent):
    p = make_player(api)
    give(p["id"], 100)
    box = _box(label)
    reward = open_box(api, box.id).get_json()["reward"]
    assert (reward["label"], reward["kind"], reward["value_cents"], reward["value_percent"]) == (label, kind, cents, percent)
    assert diamonds(p["id"]) == 100 - box.cost_diamonds


def test_retrying_the_same_open_never_charges_or_rewards_twice(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 20)
    box = _box("$2 Free Play")
    first = open_box(api, box.id, 1).get_json()
    again = open_box(api, box.id, 1)
    assert again.status_code == 200 and again.get_json()["reward"]["id"] == first["reward"]["id"] and again.get_json()["replay"] is True
    assert diamonds(p["id"]) == 15 and PlayerReward.query.count() == 1
    assert open_box(api, box.id, 2).status_code == 201 and diamonds(p["id"]) == 10  # a genuinely new open


def test_two_opens_with_diamonds_for_one_only_succeed_once(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 5)
    box = _box("$2 Free Play")
    assert open_box(api, box.id, 1).status_code == 201
    assert open_box(api, box.id, 2).status_code == 402
    assert diamonds(p["id"]) == 0 and PlayerReward.query.count() == 1


def test_inactive_or_missing_box_cannot_be_opened(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 50)
    box = _box("$2 Free Play")
    box.is_active = False
    db.session.commit()
    assert open_box(api, box.id).status_code == 404 and open_box(api, 9999, 3).status_code == 404
    assert box.id not in {b["id"] for b in get(api)["boxes"]} and diamonds(p["id"]) == 50
    assert api.post(f'/api/v1/bonus/boxes/{box.id}/open', {}).status_code == 400  # missing request id


def test_past_wins_are_a_snapshot_not_affected_by_later_edits(api, make_player, zone):
    p = make_player(api)
    give(p["id"], 10)
    box = _box("$2 Free Play")
    open_box(api, box.id)
    box.prize_cents, box.cost_diamonds, box.name = 9900, 1, "Renamed"
    db.session.commit()
    r = PlayerReward.query.one()
    assert (r.label, r.value_cents, r.cost_diamonds, r.box_name) == ("$2 Free Play", 200, 5, "Starter Gift")


# ------------------------------------------------------------------ admin
def test_admin_can_tune_task_rewards_within_bounds(zone, staff_client, api, make_player):
    root = staff_client("root", "superadmin")
    tid = BonusTask.query.filter_by(key="daily_login").one().id
    assert root.patch(f'/api/v1/admin/bonus-tasks/{tid}', {"reward_diamonds": 3}).status_code == 200
    for bad in (0, -1, 5000, "x"):
        assert root.patch(f'/api/v1/admin/bonus-tasks/{tid}', {"reward_diamonds": bad}).status_code == 400
    p = make_player(api)
    assert claim(api, 'daily_login').get_json()["diamonds_awarded"] == 3


def test_task_rules_cannot_be_edited_from_the_admin_panel(zone, staff_client):
    root = staff_client("root", "superadmin")
    t = BonusTask.query.filter_by(key="first_deposit").one()
    root.patch(f'/api/v1/admin/bonus-tasks/{t.id}', {"key": "daily_login", "kind": "daily", "group": "streak"})
    t = db.session.get(BonusTask, t.id)
    assert (t.key, t.kind, t.group) == ("first_deposit", "one_time", "daily")


def test_boxes_are_managed_through_the_admin_crud_and_validated(zone, staff_client):
    content = staff_client("editor", "content")
    r = content.post('/api/v1/admin/bonus-boxes', {"name": "Mega", "tone": "gold", "cost_diamonds": 40,
                                                   "prize_kind": "bonus_cash", "prize_cents": 1000})
    assert r.status_code == 201 and r.get_json()["prize_label"] == "$10 Bonus"
    assert content.post('/api/v1/admin/bonus-boxes', {"name": "X", "tone": "neon", "cost_diamonds": 1, "prize_kind": "freeplay"}).status_code == 400
    assert content.post('/api/v1/admin/bonus-boxes', {"name": "X", "tone": "gold", "cost_diamonds": 1, "prize_kind": "jackpot"}).status_code == 400


def test_players_and_support_cannot_edit_boxes_or_tasks(api, make_player, zone, staff_client):
    make_player(api)
    assert api.post('/api/v1/admin/bonus-boxes', {"name": "x"}).status_code == 403
    helper = staff_client("helper", "support")
    assert helper.post('/api/v1/admin/bonus-boxes', {"name": "x"}).status_code == 403
    assert helper.get('/api/v1/admin/bonus-tasks').status_code == 403


def test_rewards_have_no_staff_apply_step(api, make_player, zone, staff_client):
    p = make_player(api)
    give(p["id"], 5)
    open_box(api, _box("$2 Free Play").id)
    rid = PlayerReward.query.one().id
    helper = staff_client("helper", "support")
    listed = helper.get('/api/v1/admin/bonus-rewards').get_json()["items"]  # read-only history for support
    assert listed[0]["reward"] == "$2 Free Play" and listed[0]["status"] == "applied"
    assert helper.patch(f'/api/v1/admin/bonus-rewards/{rid}', {"status": "fulfilled"}).status_code in (404, 405)


def test_diamond_adjustments_are_superadmin_only_audited_and_never_negative(api, make_player, zone, staff_client):
    p = make_player(api)
    helper = staff_client("helper", "support")
    assert helper.post(f'/api/v1/admin/players/{p["id"]}/diamonds', {"amount": 5, "reason": "goodwill"}).status_code == 403
    root = staff_client("root", "superadmin")
    assert root.post(f'/api/v1/admin/players/{p["id"]}/diamonds', {"amount": 5, "reason": "goodwill"}).get_json()["diamonds"] == 5
    assert root.post(f'/api/v1/admin/players/{p["id"]}/diamonds', {"amount": -9, "reason": "correction"}).status_code == 409
    assert root.post(f'/api/v1/admin/players/{p["id"]}/diamonds', {"amount": 5, "reason": ""}).status_code == 400
    assert root.post(f'/api/v1/admin/players/{p["id"]}/diamonds', {"amount": 0, "reason": "none"}).status_code == 400
    assert diamonds(p["id"]) == 5
    assert "bonus.diamonds_adjust" in [a["action"] for a in root.get('/api/v1/admin/audit').get_json()["items"]]


def test_diamond_ledger_credit_is_idempotent_and_debit_is_compare_and_set(make_player, api):
    p = make_player(api)
    assert bonus.credit_diamonds(p["id"], 5, 'task', 'x', 1) is True
    assert bonus.credit_diamonds(p["id"], 5, 'task', 'x', 1) is False
    db.session.commit()
    assert diamonds(p["id"]) == 5
    with pytest.raises(bonus.InsufficientDiamonds):
        bonus.debit_diamonds(p["id"], 6, 'box', 'y', 1)
    db.session.rollback()
    assert diamonds(p["id"]) == 5


def test_sandbox_registration_grants_test_diamonds_but_normal_mode_never_does(app, api, make_player, zone, features):
    p = make_player(api)
    assert diamonds(p["id"]) == 0 and get(api)["sandbox_notice"] is None
    features(sandbox=True)
    from tests.conftest import Api
    other = Api(app.test_client())
    q = make_player(other, username="sandbox_user", email="sb@example.com")
    assert diamonds(q["id"]) == 30
    z = other.get('/api/v1/bonus').get_json()
    assert "Sandbox" in z["sandbox_notice"] and z["diamonds"] == 30
