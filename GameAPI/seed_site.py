"""
Seed JamesVault site data. Safe to run repeatedly.

  python seed_site.py                 # catalog entries from the real Provider rows; superadmins from ADMIN_EMAILS
  python seed_site.py --dev-sample    # ALSO adds clearly-labelled [SAMPLE] promotions/tournament (development only)

Superadmin accounts are pre-created for the emails in ADMIN_EMAILS (no password is ever set or printed).
"""
import os
import re
import secrets
import sys
from datetime import timedelta

from app import create_app, db
from app.models import Provider
from app.models_site import CatalogGame, Player, Promotion, Tournament
from app.services.bonus import ensure_defaults
from app.services.wheel import ensure_default_prizes
from app.utils.auth import utcnow

app = create_app()


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def seed_admins():
    """Pre-create superadmin player accounts for ADMIN_EMAILS. They get an unusable random password;
    the owner sets their own via "Forgot password" (proves control of the inbox). Registration never
    grants a role, so a reserved address cannot be claimed by someone else signing up."""
    for email in app.config["ADMIN_EMAILS"]:
        player = Player.query.filter_by(email=email).first()
        if player:
            if player.role != 'superadmin':
                player.role = 'superadmin'
                print(f"Promoted existing player {player.username} <{email}> to superadmin.")
            continue
        base = re.sub(r'[^A-Za-z0-9_]', '', email.split('@')[0])[:24] or 'admin'
        username, n = base, 1
        while Player.query.filter(db.func.lower(Player.username) == username.lower()).first():
            n += 1
            username = f"{base}{n}"
        player = Player(username=username, email=email, role='superadmin')
        player.set_password(secrets.token_urlsafe(32))
        db.session.add(player)
        print(f"Created superadmin {username} <{email}>. Use 'Forgot password' on /login to set a password.")


def seed_catalog():
    """First-time setup only: one catalog entry per provider. Once the catalog has any game, the admins own it (add, edit and
    delete in Admin -> Game catalog), so a deleted game is never brought back by a later deploy."""
    if CatalogGame.query.count():
        print("Catalog already set up; not adding games automatically.")
        return
    created = 0
    for provider in Provider.query.all():
        slug = slugify(provider.name)
        if CatalogGame.query.filter_by(slug=slug).first():
            continue
        db.session.add(CatalogGame(
            slug=slug, name=provider.name, provider_id=provider.id,
            category=provider.category.name.replace('CATEGORY', 'Category '),
            status='active', launch_supported=False,
            description="Listing only. Launching is not available until a provider launch integration is configured.",
        ))
        created += 1
    print(f"Catalog entries created: {created}")


def seed_dev_sample():
    now = utcnow()
    if not Promotion.query.filter_by(slug='sample-welcome').first():
        db.session.add(Promotion(
            slug='sample-welcome', title='[SAMPLE] Welcome offer', promo_type='welcome', claim_rule='new_player',
            description='Development sample only. Not a real offer.',
            eligibility='New players within 7 days of registering.',
            reward_details='Sample - no real reward.', terms='Sample promotion for UI development.',
            starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=30), is_active=True,
        ))
    if not Tournament.query.filter_by(slug='sample-weekly').first():
        db.session.add(Tournament(
            slug='sample-weekly', title='[SAMPLE] Weekly tournament',
            description='Development sample only.', rules='Sample rules.', prize_info='No real prize.',
            starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=6), is_active=True,
        ))


with app.app_context():
    db.create_all()
    from app.utils.schema import add_missing_columns
    add_missing_columns()  # new columns on tables that already exist (additive only)
    seed_admins()
    seed_catalog()
    ensure_defaults()
    ensure_default_prizes()
    if "--dev-sample" in sys.argv:
        if os.getenv("JV_ENV") == "production":
            sys.exit("Refusing to add sample data in production.")
        seed_dev_sample()
    db.session.commit()
    print("Site seed complete.")
