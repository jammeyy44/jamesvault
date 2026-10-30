"""
Keep only some games in the catalog and remove the rest. Run from the GameAPI folder with the virtualenv active.

    python catalog_keep.py game-vault juwa          # preview: shows what would be removed, changes nothing
    python catalog_keep.py game-vault juwa --yes    # do it

A game that players already have logins for is never deleted (their logins and history would break): it is hidden from the
site instead and listed as "hidden". Everything else is deleted together with its favourites. Providers are not touched.
Find a game's slug in Admin -> Game catalog (the "Slug" field).
"""
import sys

from app import app, db
from app.models_site import CatalogGame, Favorite, GameAccount


def main(argv):
    apply = "--yes" in argv
    keep = {a.strip().lower() for a in argv if not a.startswith("--")}
    if not keep:
        raise SystemExit(__doc__)
    with app.app_context():
        games = CatalogGame.query.order_by(CatalogGame.id).all()
        missing = keep - {g.slug for g in games}
        if missing:
            raise SystemExit(f"No game with slug {', '.join(sorted(missing))}. Existing slugs: {', '.join(g.slug for g in games)}")
        for g in games:
            if g.slug in keep:
                print(f"KEEP    {g.slug:<28} {g.name}")
                continue
            logins = GameAccount.query.filter_by(game_id=g.id).count()
            if logins:
                print(f"HIDE    {g.slug:<28} {g.name}  ({logins} player login(s) exist, so it is hidden, not deleted)")
                if apply:
                    g.status = "hidden"
            else:
                print(f"DELETE  {g.slug:<28} {g.name}")
                if apply:
                    Favorite.query.filter_by(game_id=g.id).delete()
                    db.session.delete(g)
        if apply:
            db.session.commit()
            print("\nDone.")
        else:
            print("\nPreview only. Run again with --yes to apply.")


if __name__ == "__main__":
    main(sys.argv[1:])
