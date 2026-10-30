"""Catalog, promotions, rewards, referrals, tournaments, support and admin authorization."""
from datetime import timedelta

from app import db
from app.models_site import CatalogGame, Notification, Promotion, PromotionClaim, Referral
from app.utils.auth import utcnow


def _promo(**kw):
    now = utcnow()
    defaults = dict(slug="promo", title="Promo", is_active=True, claim_rule="open", repeat="once",
                    starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=1))
    defaults.update(kw)
    p = Promotion(**defaults)
    db.session.add(p)
    db.session.commit()
    return p


# --- catalog / launch
def test_catalog_hides_hidden_games_and_filters(api):
    db.session.add_all([CatalogGame(slug="a", name="Alpha"), CatalogGame(slug="b", name="Bravo", status="hidden")])
    db.session.commit()
    items = api.get('/api/v1/games').get_json()["items"]
    assert [g["slug"] for g in items] == ["a"]
    assert api.get('/api/v1/games?search=zzz').get_json()["total"] == 0
    assert api.get('/api/v1/games/b').status_code == 404


def test_game_launch_never_simulates_success(api, make_player):
    db.session.add(CatalogGame(slug="a", name="Alpha", launch_supported=True))
    db.session.commit()
    assert api.post('/api/v1/games/a/launch').status_code == 401
    make_player(api)
    r = api.post('/api/v1/games/a/launch')
    assert r.status_code == 501 and r.get_json()["code"] == "launch_unsupported"


def test_favorites(api, make_player):
    db.session.add(CatalogGame(slug="a", name="Alpha"))
    db.session.commit()
    make_player(api)
    assert api.put('/api/v1/favorites/a').status_code == 200
    assert api.put('/api/v1/favorites/a').status_code == 200  # idempotent
    assert api.get('/api/v1/games').get_json()["items"][0]["favorite"] is True
    assert api.get('/api/v1/games?favorites=1').get_json()["total"] == 1
    api.delete('/api/v1/favorites/a')
    assert api.get('/api/v1/games?favorites=1').get_json()["total"] == 0


# --- promotions
def test_promotion_claim_only_once(api, make_player):
    _promo()
    make_player(api)
    assert api.post('/api/v1/promotions/promo/claim').status_code == 201
    assert api.post('/api/v1/promotions/promo/claim').status_code == 409
    assert PromotionClaim.query.count() == 1


def test_promotion_window_and_requirements(api, make_player):
    now = utcnow()
    _promo(slug="ended", ends_at=now - timedelta(hours=1))
    _promo(slug="future", starts_at=now + timedelta(hours=1))
    _promo(slug="off", is_active=False)
    _promo(slug="coupon", claim_rule="coupon", coupon_code="SECRET")
    _promo(slug="deposit", claim_rule="deposit")
    make_player(api)
    for slug in ("ended", "future"):
        assert api.post(f'/api/v1/promotions/{slug}/claim').status_code == 409
    assert api.post('/api/v1/promotions/off/claim').status_code == 404
    assert api.post('/api/v1/promotions/deposit/claim').status_code == 409
    assert api.post('/api/v1/promotions/coupon/claim', {"coupon": "wrong"}).status_code == 403
    assert api.post('/api/v1/promotions/coupon/claim', {"coupon": "secret"}).status_code == 201


def test_new_player_promotion_blocks_old_accounts(api, make_player):
    _promo(slug="welcome", claim_rule="new_player", new_player_days=7)
    player = make_player(api)
    from app.models_site import Player
    db.session.get(Player, player["id"]).created_at = utcnow() - timedelta(days=30)
    db.session.commit()
    assert api.post('/api/v1/promotions/welcome/claim').status_code == 403


def test_public_promotion_listing_hides_coupon_codes_and_inactive(api):
    _promo(slug="coupon", claim_rule="coupon", coupon_code="SECRET")
    _promo(slug="off", is_active=False)
    body = api.get('/api/v1/promotions').get_data(as_text=True)
    assert "SECRET" not in body and '"off"' not in body


# --- referrals
def test_referral_attribution_is_pending_until_staff_confirm(api, app, make_player, admin_api):
    referrer = make_player(api)
    other = app.test_client()
    from tests.conftest import Api
    other_api = Api(other)
    make_player(other_api, username="friend_one", email="f@example.com", referral_code=referrer["referral_code"])
    ref = Referral.query.one()
    assert ref.status == "pending" and ref.referrer_id == referrer["id"]
    body = api.get('/api/v1/referrals/me').get_json()
    assert body["counts"]["pending"] == 1 and body["items"][0]["player"] != "friend_one"  # masked
    assert admin_api.patch(f'/api/v1/admin/referrals/{ref.id}', {"status": "confirmed"}).status_code == 200
    assert admin_api.patch(f'/api/v1/admin/referrals/{ref.id}', {"status": "confirmed"}).status_code == 409


def test_unknown_referral_code_is_ignored(api, make_player):
    make_player(api, referral_code="NOPE1234")
    assert Referral.query.count() == 0


# --- tournaments
def test_tournament_leaderboard_masks_and_scores_are_admin_only(api, app, make_player, admin_api):
    from app.models_site import Tournament
    now = utcnow()
    admin_api.post('/api/v1/admin/tournaments', {
        "slug": "t1", "title": "T1", "starts_at": (now - timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=1)).isoformat(), "is_active": True})
    make_player(api)
    assert api.post('/api/v1/tournaments/t1/join').status_code == 201
    assert api.post('/api/v1/tournaments/t1/join').status_code == 409
    entry_id = admin_api.get('/api/v1/admin/tournaments/%d/entries' % Tournament.query.one().id).get_json()["items"][0]["id"]
    assert api.patch(f'/api/v1/admin/entries/{entry_id}', {"score": 999}).status_code == 403  # players cannot score
    assert admin_api.patch(f'/api/v1/admin/entries/{entry_id}', {"score": "12.50"}).status_code == 200
    board = api.get('/api/v1/tournaments/t1').get_json()
    assert board["leaderboard"][0]["score"] == "12.50"
    assert board["leaderboard"][0]["player"] == "pl***e"
    assert board["my_entry"]["rank"] == 1


def test_cannot_join_completed_tournament(api, make_player, admin_api):
    now = utcnow()
    admin_api.post('/api/v1/admin/tournaments', {
        "slug": "old", "title": "Old", "starts_at": (now - timedelta(days=3)).isoformat(),
        "ends_at": (now - timedelta(days=1)).isoformat(), "is_active": True})
    make_player(api)
    assert api.post('/api/v1/tournaments/old/join').status_code == 409


# --- support
def test_support_tickets_are_private_to_their_owner(api, app, make_player):
    make_player(api)
    t = api.post('/api/v1/support/tickets', {"subject": "Help me", "message": "Something broke"}).get_json()["ticket"]
    from tests.conftest import Api
    other = Api(app.test_client())
    make_player(other, username="someone_else", email="s@example.com")
    assert other.get(f'/api/v1/support/tickets/{t["id"]}').status_code == 404
    assert api.get(f'/api/v1/support/tickets/{t["id"]}').status_code == 200


def test_staff_reply_notifies_player(api, make_player, admin_api):
    make_player(api)
    t = api.post('/api/v1/support/tickets', {"subject": "Help me", "message": "Something broke"}).get_json()["ticket"]
    assert admin_api.post(f'/api/v1/admin/tickets/{t["id"]}/reply', {"message": "On it"}).status_code == 200
    assert api.get(f'/api/v1/support/tickets/{t["id"]}').get_json()["status"] == "answered"
    assert Notification.query.filter_by(title="Support replied").count() == 1


# --- admin authorization
def test_admin_endpoints_reject_anonymous_and_players(api, make_player):
    urls = ('/api/v1/admin/overview', '/api/v1/admin/players', '/api/v1/admin/audit', '/api/v1/admin/tokens')
    for url in urls:
        assert api.get(url).status_code == 401
    make_player(api)
    for url in urls:
        assert api.get(url).status_code == 403


def test_support_role_cannot_manage_content_or_audit(staff_client):
    helper = staff_client("helper", "support")
    assert helper.post('/api/v1/admin/games', {"slug": "x", "name": "X"}).status_code == 403
    assert helper.get('/api/v1/admin/audit').status_code == 403
    assert helper.get('/api/v1/admin/players').status_code == 200


def test_signup_can_never_grant_staff_role(api):
    r = api.post('/api/v1/auth/register', {"username": "sneaky", "email": "s@example.com", "password": "Sup3rSecret!x",
                                           "accept_terms": True, "role": "superadmin", "is_admin": True})
    assert r.status_code == 201
    assert r.get_json()["player"]["role"] == "player" and r.get_json()["player"]["is_admin"] is False
    assert api.get('/api/v1/admin/overview').status_code == 403


def test_reserved_admin_email_cannot_be_claimed_by_registration(app, api):
    from app.models_site import Player
    owner = Player(username="owner", email="jammeyy44@gmail.com", role="superadmin")
    owner.set_password("unusable-random-value-123")
    db.session.add(owner)
    db.session.commit()
    r = api.post('/api/v1/auth/register', {"username": "attacker", "email": "Jammeyy44@gmail.com",
                                           "password": "Sup3rSecret!x", "accept_terms": True})
    assert r.status_code == 409


def test_only_superadmin_can_change_roles_and_not_their_own(staff_client, make_player, app):
    from app.models_site import Player
    from tests.conftest import Api
    root = staff_client("root", "superadmin")
    helper = staff_client("helper", "support")
    other = Api(app.test_client())
    victim = make_player(other, username="regular_joe", email="joe@example.com")
    assert helper.patch(f'/api/v1/admin/players/{victim["id"]}', {"role": "superadmin"}).status_code == 403
    assert root.patch(f'/api/v1/admin/players/{victim["id"]}', {"role": "content"}).status_code == 200
    assert db.session.get(Player, victim["id"]).role == "content"
    root_id = Player.query.filter_by(username="root").one().id
    assert root.patch(f'/api/v1/admin/players/{root_id}', {"role": "player"}).status_code == 409
    assert root.patch(f'/api/v1/admin/players/{victim["id"]}', {"role": "emperor"}).status_code == 400


def test_suspended_staff_lose_access(staff_client):
    from app.models_site import Player
    root = staff_client("root", "superadmin")
    assert root.get('/api/v1/admin/overview').status_code == 200
    Player.query.filter_by(username="root").update({"status": "suspended"})
    db.session.commit()
    assert root.get('/api/v1/admin/overview').status_code == 401 or root.get('/api/v1/admin/overview').status_code == 403


def test_admin_crud_and_audit_trail(admin_api):
    r = admin_api.post('/api/v1/admin/games', {"slug": "new-game", "name": "New Game", "category": "slots"})
    assert r.status_code == 201
    assert admin_api.post('/api/v1/admin/games', {"slug": "new-game", "name": "Dup"}).status_code == 409
    gid = r.get_json()["id"]
    assert admin_api.patch(f'/api/v1/admin/games/{gid}', {"status": "bogus"}).status_code == 400
    assert admin_api.patch(f'/api/v1/admin/games/{gid}', {"status": "maintenance"}).status_code == 200
    actions = [a["action"] for a in admin_api.get('/api/v1/admin/audit').get_json()["items"]]
    assert "games.create" in actions and "games.update" in actions


def test_admin_provider_listing_never_exposes_credentials(admin_api):
    from app.models import Provider, RemoteProvider
    db.session.add(Provider(name="P", category=RemoteProvider.CATEGORY1, base_url="https://x", username="u", password="topsecret"))
    db.session.commit()
    body = admin_api.get('/api/v1/admin/providers').get_data(as_text=True)
    assert "topsecret" not in body and '"password"' not in body
