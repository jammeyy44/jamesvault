"""Adds the known game panels to the Providers list WITHOUT credentials.

Run once, then open Admin -> Providers and enter each panel's agent login (Category 6 panels: agent ID as the username and the
secret key as the password). Providers are created switched OFF until they have credentials. Existing rows are never touched.
Never put real credentials in this file: it is committed to git.
"""
from app import create_app, db
from app.models import Provider, RemoteProvider

app = create_app()

# (name, category, base_url). Check the base URLs with each provider.
PROVIDERS = [
    ("Gameroom", "CATEGORY1", "https://agentserver.gameroom777.com"),
    ("Cash Machine", "CATEGORY1", "http://agentserver.cashmachine777.com:8003"),
    ("Mr All In One", "CATEGORY1", "http://agentserver.mrallinone777.com"),
    ("Cash Frenzy", "CATEGORY1", "http://agentserver.cashfrenzy777.com:8003"),
    ("Mafia", "CATEGORY1", "http://agentserver.mafia77777.com:8003"),
    ("King of Pop", "CATEGORY1", "http://agentserver.slots88888.com:8003"),
    ("Game Vault", "CATEGORY6", "https://agent.gamevault999.com"),
    ("Vegas Sweeps", "CATEGORY6", "https://agent.lasvegassweeps.com"),
    ("Juwa", "CATEGORY6", "https://ht.juwa777.com"),
    ("Orion Stars", "CATEGORY3", "https://orionstars.vip:8781"),
    ("Panda Master", "CATEGORY3", "https://www.pandamaster.vip"),
    ("Milkyway", "CATEGORY3", "https://milkywayapp.xyz:8781"),
    ("Fire Kirin", "CATEGORY3", "https://firekirin.xyz:8888"),
    ("River Sweeps", "CATEGORY4", "https://river-pay.com"),
    ("Vblink", "CATEGORY5", "https://gm.vblink777.club"),
    ("Egame", "CATEGORY5", "https://pko.egame99.club"),
    ("Ultra Panda", "CATEGORY5", "https://ht.ultrapanda.mobi"),
]

with app.app_context():
    added = 0
    for name, category, base_url in PROVIDERS:
        if Provider.query.filter_by(name=name).first():
            continue
        db.session.add(Provider(name=name, category=RemoteProvider[category], base_url=base_url,
                                username="CHANGE_ME", password="CHANGE_ME", is_active=False))
        added += 1
    db.session.commit()
    print(f"Providers added: {added} (switched off until you enter their credentials in Admin -> Providers)")
