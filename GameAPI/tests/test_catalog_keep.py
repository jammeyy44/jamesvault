"""Removing games from the catalog safely, and not bringing them back on the next deploy."""
import subprocess
import sys

from app import db
from app.models import Provider, RemoteProvider
from app.models_site import CatalogGame, Favorite, GameAccount, Player

import catalog_keep
import seed_site


def _games():
    for slug, name in (("game-vault", "Game Vault"), ("juwa", "Juwa"), ("royal-vault", "Royal Vault"), ("estar", "EStar"), ("vblink", "VBlink")):
        db.session.add(CatalogGame(slug=slug, name=name, category="Slots"))
    db.session.commit()


def test_preview_changes_nothing(app, capsys):
    _games()
    catalog_keep.main(["game-vault", "juwa"])
    assert CatalogGame.query.count() == 5
    out = capsys.readouterr().out
    assert "DELETE  royal-vault" in out and "KEEP    juwa" in out and "Preview only" in out


def test_yes_deletes_the_others_and_their_favourites(app):
    _games()
    p = Player(username="fan", email="fan@example.com")
    p.set_password("Sup3rSecret!x")
    db.session.add(p)
    db.session.flush()
    db.session.add(Favorite(player_id=p.id, game_id=CatalogGame.query.filter_by(slug="estar").one().id))
    db.session.commit()
    catalog_keep.main(["game-vault", "juwa", "--yes"])
    assert sorted(g.slug for g in CatalogGame.query.all()) == ["game-vault", "juwa"]
    assert Favorite.query.count() == 0


def test_a_game_players_have_logins_for_is_hidden_not_deleted(app):
    _games()
    p = Player(username="owner", email="owner@example.com")
    p.set_password("Sup3rSecret!x")
    db.session.add(p)
    db.session.flush()
    db.session.add(GameAccount(player_id=p.id, game_id=CatalogGame.query.filter_by(slug="vblink").one().id, provider_username="x1",
                               password_enc="x", status="active"))
    db.session.commit()
    catalog_keep.main(["game-vault", "juwa", "--yes"])
    vblink = CatalogGame.query.filter_by(slug="vblink").one()
    assert vblink.status == "hidden" and CatalogGame.query.filter_by(slug="estar").first() is None


def test_an_unknown_slug_stops_before_changing_anything(app):
    _games()
    try:
        catalog_keep.main(["game-vault", "nope", "--yes"])
        assert False, "should have stopped"
    except SystemExit as e:
        assert "nope" in str(e)
    assert CatalogGame.query.count() == 5


def test_seeding_does_not_bring_back_deleted_games(app):
    db.session.add(Provider(name="Juwa", category=RemoteProvider.CATEGORY6, base_url="https://x.example.com", username="1", password="k"))
    db.session.add(Provider(name="Game Vault", category=RemoteProvider.CATEGORY6, base_url="https://y.example.com", username="2", password="k"))
    db.session.commit()
    seed_site.seed_catalog()                                  # first run on an empty catalog: one game per provider
    assert CatalogGame.query.count() == 2
    db.session.delete(CatalogGame.query.filter_by(slug="juwa").one())
    db.session.commit()
    seed_site.seed_catalog()                                  # a later deploy must leave the admin's choice alone
    assert [g.slug for g in CatalogGame.query.all()] == ["game-vault"]


# ------------------------------------------------------------------ the Admin delete button
def test_admin_can_delete_a_game_that_only_has_favourites(app, staff_client):
    _games()
    root = staff_client("root", "superadmin")
    fan = Player(username="fan2", email="fan2@example.com")
    fan.set_password("Sup3rSecret!x")
    db.session.add(fan)
    db.session.flush()
    gid = CatalogGame.query.filter_by(slug="estar").one().id
    db.session.add(Favorite(player_id=fan.id, game_id=gid))
    db.session.commit()
    assert root.delete(f'/api/v1/admin/games/{gid}').status_code == 200
    assert CatalogGame.query.filter_by(slug="estar").first() is None and Favorite.query.count() == 0


def test_admin_cannot_delete_a_game_with_player_logins_and_is_told_to_hide_it(app, staff_client):
    _games()
    root = staff_client("root", "superadmin")
    owner = Player(username="owner2", email="owner2@example.com")
    owner.set_password("Sup3rSecret!x")
    db.session.add(owner)
    db.session.flush()
    gid = CatalogGame.query.filter_by(slug="vblink").one().id
    db.session.add(GameAccount(player_id=owner.id, game_id=gid, provider_username="x2", password_enc="x", status="active"))
    db.session.commit()
    r = root.delete(f'/api/v1/admin/games/{gid}')
    assert r.status_code == 409 and r.get_json()["code"] == "has_logins" and "Hide it instead" in r.get_json()["error"]
    assert root.patch(f'/api/v1/admin/games/{gid}', {"status": "hidden"}).status_code == 200
    assert CatalogGame.query.get(gid).status == "hidden"
