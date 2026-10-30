# seed_admins.py
# Creates the legacy provider-API admin with a random password that is shown once. (Site staff sign in through the normal
# login with a role; see seed_site.py.) Never commit a fixed password here.
import secrets

from app import create_app, db
from app.models import Admin

app = create_app()

with app.app_context():
    if Admin.query.filter_by(username='admin').first():
        print("Admin account already exists; nothing changed.")
    else:
        password = secrets.token_urlsafe(16)
        admin = Admin(username='admin')
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin account created. Username: admin  Password: {password}  (shown once; store it safely)")
