"""Who is on the support team, as far as players may know: anonymous aliases and a real-activity 'online' signal."""
import re
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app import db
from app.models_site import OperatorAlias, TeamActivity
from app.utils.auth import utcnow

ALIAS_RE = re.compile(r"^Operator \d+$")
TYPING_SECONDS = 15


def alias_for(telegram_user_id) -> str:
    """'Operator N' for this team member (the same member always gets the same number)."""
    uid = int(telegram_user_id or 0)
    row = OperatorAlias.query.filter_by(telegram_user_id=uid).first()
    for _ in range(5):
        if row:
            return f"Operator {row.number}"
        nxt = (db.session.query(db.func.max(OperatorAlias.number)).scalar() or 0) + 1
        row = OperatorAlias(telegram_user_id=uid, number=nxt)
        db.session.add(row)
        try:
            db.session.flush()
        except IntegrityError:  # two first-timers at once
            db.session.rollback()
            row = OperatorAlias.query.filter_by(telegram_user_id=uid).first()
    return f"Operator {row.number}" if row else "Operator"


def display_name(stored) -> str:
    """What a player sees. Older rows that stored a real name are shown as a plain 'Operator'."""
    return stored if stored and ALIAS_RE.match(stored) else "Operator"


def touch_presence():
    """Note that the team did something just now (writes at most every 20 seconds)."""
    now = utcnow()
    row = db.session.get(TeamActivity, 1)
    if row is None:
        db.session.add(TeamActivity(id=1, last_active_at=now))
    elif now - row.last_active_at > timedelta(seconds=20):
        row.last_active_at = now


def operators_online() -> bool:
    """True when someone on the team was active in the group within the last OPERATORS_ONLINE_MINUTES (default 10)."""
    row = db.session.get(TeamActivity, 1)
    minutes = int(current_app.config.get("OPERATORS_ONLINE_MINUTES") or 10)
    return bool(row and utcnow() - row.last_active_at <= timedelta(minutes=minutes))
