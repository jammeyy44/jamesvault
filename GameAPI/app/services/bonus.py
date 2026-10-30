"""
Bonus Zone engine: diamonds ledger, task verification and defaults.

Diamonds are an integer balance on the player row changed only by atomic conditional UPDATEs plus an append-only
DiamondEntry (unique kind/ref makes every movement idempotent). Tasks are verified from server-side facts only
(email verified, wallet ledger, confirmed referrals, tournament entries, daily visits); nothing is trusted from the client.
"""
from datetime import date, timedelta

from flask import current_app
from sqlalchemy import update

from app import db
from app.models_site import (
    BonusBox, BonusTask, DepositBoost, DiamondEntry, Player, Referral, TaskClaim, WalletEntry,
)
from app.services import wallet as ledger
from app.utils.auth import utcnow


class InsufficientDiamonds(Exception):
    pass


def _exists(kind, ref_type, ref_id):
    return DiamondEntry.query.filter_by(kind=kind, ref_type=ref_type, ref_id=str(ref_id)).first() is not None


def credit_diamonds(player_id, n, kind, ref_type, ref_id) -> bool:
    if n <= 0:
        raise ValueError("credit must be positive")
    if _exists(kind, ref_type, ref_id):
        return False
    db.session.execute(update(Player).where(Player.id == player_id).values(diamonds=Player.diamonds + n))
    db.session.add(DiamondEntry(player_id=player_id, amount=n, kind=kind, ref_type=ref_type, ref_id=str(ref_id)))
    db.session.flush()
    return True


def debit_diamonds(player_id, n, kind, ref_type, ref_id) -> bool:
    """Atomic compare-and-set: two racing spends cannot both succeed on the same balance."""
    if n <= 0:
        raise ValueError("debit must be positive")
    if _exists(kind, ref_type, ref_id):
        return False
    res = db.session.execute(update(Player).where(Player.id == player_id, Player.diamonds >= n)
                             .values(diamonds=Player.diamonds - n))
    if res.rowcount != 1:
        raise InsufficientDiamonds()
    db.session.add(DiamondEntry(player_id=player_id, amount=-n, kind=kind, ref_type=ref_type, ref_id=str(ref_id)))
    db.session.flush()
    return True


# ------------------------------------------------------------------ tasks
def week_days(today: date):
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def _week_key(today: date) -> str:
    y, w, _ = today.isocalendar()
    return f"{y}-W{w:02d}"


def _wallet_enabled():
    return current_app.config["FEATURES"]["wallet"]


def evaluate(player, task, today: date, claimed: set, ctx: dict):
    """Returns {state: claimable|claimed|locked, reason, progress, claim_key, available}. `ctx` caches lookups."""
    k, pid = task.key, player.id
    out = {"state": "locked", "reason": None, "progress": None, "claim_key": None, "available": 0}

    def done(key):
        out.update(state="claimed", claim_key=key)
        return out

    def ready(key, available=1):
        out.update(state="claimable", claim_key=key, available=available)
        return out

    def locked(reason, progress=None):
        out.update(state="locked", reason=reason, progress=progress)
        return out

    if k == "verify_email":
        key = f"{k}:{pid}"
        if key in claimed:
            return done(key)
        return ready(key) if player.email_verified else locked("Confirm your email address first")

    if k == "daily_login":
        key = f"{k}:{pid}:{today.isoformat()}"
        return done(key) if key in claimed else ready(key)

    if k == "weekly_streak":
        days = [d for d in week_days(today) if f"daily_login:{pid}:{d.isoformat()}" in claimed]
        key = f"{k}:{pid}:{_week_key(today)}"
        out["progress"] = {"done": len(days), "total": 7}
        if key in claimed:
            return done(key)
        return ready(key) if len(days) == 7 else locked(f"{len(days)} of 7 days this week", out["progress"])

    if k in ("daily_deposit", "first_deposit"):
        if not _wallet_enabled():
            return locked("Available when deposits are enabled")
        if k == "first_deposit":
            key = f"{k}:{pid}"
            if key in claimed:
                return done(key)
            has = WalletEntry.query.filter_by(player_id=pid, kind="deposit").first() is not None
            return ready(key) if has else locked("Make your first deposit")
        key = f"{k}:{pid}:{today.isoformat()}"
        if key in claimed:
            return done(key)
        start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        total = sum(e.amount_cents for e in WalletEntry.query.filter(
            WalletEntry.player_id == pid, WalletEntry.kind == "deposit", WalletEntry.created_at >= start))
        need = int(current_app.config["DEPOSIT_TASK_MIN"] * 100)
        out["progress"] = {"done": min(total, need) // 100, "total": need // 100}
        return ready(key) if total >= need else locked(f"Deposit ${need // 100} or more today", out["progress"])

    if k == "refer_friend":
        confirmed = ctx.setdefault("refs", [r.id for r in Referral.query.filter_by(referrer_id=pid, status="confirmed")])
        open_ids = [i for i in confirmed if f"{k}:{i}" not in claimed]
        if open_ids:
            return ready(f"{k}:{open_ids[0]}", available=len(open_ids))
        return locked("Invite a friend; it counts once staff confirm their sign-up")

    return locked("Unavailable")


# ------------------------------------------------------------------ defaults (editable in the admin panel)
DEFAULT_TASKS = [
    # key, title, description, group, kind, diamonds, icon, order
    ("verify_email", "Email", "Confirm your email address to receive diamond prizes.", "general", "one_time", 2, "mail", 1),
    ("refer_friend", "Refer a friend", "Earn diamonds for every friend whose sign-up we confirm.", "general", "per_referral", 3, "users", 2),
    ("daily_login", "Daily login", "Visit every day and claim shining diamonds.", "daily", "daily", 1, "check", 1),
    ("daily_deposit", "Daily deposit", "Make a deposit of $20 or more today and get your diamond reward.", "daily", "daily", 2, "wallet", 2),
    ("first_deposit", "First deposit", "Make your first deposit and claim a diamond bonus.", "daily", "one_time", 5, "gem", 3),
    ("weekly_streak", "Weekly streak", "Log in all seven days of the week for a streak bonus.", "streak", "weekly", 5, "flame", 1),
]

DEFAULT_BOXES = [
    # name, tone, cost, kind, cents, percent, description, order
    ("Starter Gift", "gift", 5, "freeplay", 200, None, "$2 free play, added to your bonus balance instantly.", 1),
    ("Silver Chest", "crystal", 10, "freeplay", 300, None, "$3 free play, added to your bonus balance instantly.", 2),
    ("Golden Chest", "gold", 15, "freeplay", 400, None, "$4 free play, added to your bonus balance instantly.", 3),
    ("Crystal Vault", "ember", 20, "deposit_bonus_percent", None, 20, "A 20% Deposit Boost: every deposit for 24 hours earns 20% extra bonus.", 4),
    ("Emerald Treasure", "emerald", 30, "bonus_cash", 500, None, "The big one: a $5 bonus, added to your bonus balance instantly.", 5),
]


RETIRED_TASKS = {"join_tournament"}  # tournaments were removed from the product


def ensure_defaults():
    """Create the default tasks and boxes once. Never overwrites what an admin has edited. Removes retired tasks."""
    BonusTask.query.filter(BonusTask.key.in_(RETIRED_TASKS)).delete(synchronize_session=False)
    for key, title, desc, group, kind, n, icon, order in DEFAULT_TASKS:
        if not BonusTask.query.filter_by(key=key).first():
            db.session.add(BonusTask(key=key, title=title, description=desc, group=group, kind=kind,
                                     reward_diamonds=n, icon=icon, sort_order=order, is_active=True))
    # Refresh descriptions that are still the previous default text (rewards used to be staff-applied).
    OLD_DESCRIPTIONS = {
        "A $2 free play reward.": DEFAULT_BOXES[0][6], "A $3 free play reward.": DEFAULT_BOXES[1][6],
        "A $4 free play reward.": DEFAULT_BOXES[2][6], "A 20% bonus on your next deposit.": DEFAULT_BOXES[3][6],
        "The big one: a $5 bonus.": DEFAULT_BOXES[4][6],
    }
    for box in BonusBox.query.all():
        if box.description in OLD_DESCRIPTIONS:
            box.description = OLD_DESCRIPTIONS[box.description]
    if BonusBox.query.count() == 0:
        for name, tone, cost, kind, cents, pct, desc, order in DEFAULT_BOXES:
            db.session.add(BonusBox(name=name, tone=tone, cost_diamonds=cost, prize_kind=kind, prize_cents=cents,
                                    prize_percent=pct, description=desc, sort_order=order, is_active=True))


# ------------------------------------------------------------------ deposit boost + instant rewards
def active_boost(player_id, now=None):
    now = now or utcnow()
    row = DepositBoost.query.filter_by(player_id=player_id).first()
    return row if row is not None and row.expires_at > now else None


def activate_boost(player_id, percent: int, hours: int):
    """Start (or extend) a boost. A running boost keeps the better percentage and the later expiry, so opening a second
    boost box never shortens or weakens one that is already running."""
    now = utcnow()
    new_expiry = now + timedelta(hours=hours)
    row = DepositBoost.query.filter_by(player_id=player_id).first()
    if row is None:
        row = DepositBoost(player_id=player_id, percent=percent, expires_at=new_expiry)
        db.session.add(row)
    elif row.expires_at <= now:
        row.percent, row.expires_at = percent, new_expiry
    else:
        row.percent, row.expires_at = max(row.percent, percent), max(row.expires_at, new_expiry)
    db.session.flush()
    return row


def grant_deposit_bonus(order) -> int:
    """Credit the boost bonus for a PAID deposit order to the bonus balance (once). The percentage is the snapshot taken
    when the order was created, so a deposit that was started during the boost still gets it if payment lands later."""
    if not order.bonus_percent or order.bonus_cents:
        return 0
    cents = ledger.percent_of(order.amount_cents, order.bonus_percent)
    if cents > 0 and ledger.credit(order.player_id, cents, "deposit_bonus", "payment_order", order.id, bucket="bonus"):
        order.bonus_cents = cents
        return cents
    return 0


def grant_referral_bonus(referred_id, amount_cents, order=None) -> int:
    """The referred player's first credited deposit pays their referrer a bonus-balance reward (once, ever).

    Returns the cents paid (0 when nothing was due). Not paid for: a deposit under the minimum, a referral staff rejected, a
    referral already rewarded, a suspended referrer, or a self-referral. Idempotent through the ledger."""
    from flask import current_app
    from app.models_site import Notification
    ref = Referral.query.filter_by(referred_id=referred_id).first()
    if ref is None or ref.status in ("rejected", "reversed") or ref.reward_cents or ref.referrer_id == ref.referred_id:
        return 0
    if amount_cents < int(current_app.config["DEPOSIT_MIN"] * 100):
        return 0
    referrer = db.session.get(Player, ref.referrer_id)
    if referrer is None or referrer.status != "active":
        return 0
    cents = int(current_app.config.get("REFERRAL_BONUS_CENTS") or 0)
    if cents <= 0 or not ledger.credit(ref.referrer_id, cents, "referral_bonus", "referral", ref.id, bucket="bonus"):
        return 0
    ref.reward_cents, ref.status, ref.confirmed_at = cents, "confirmed", utcnow()
    ref.qualifying_order_id = getattr(order, "id", None)
    db.session.add(Notification(player_id=ref.referrer_id, title="Referral bonus",
                                body=f"${cents / 100:g} was added to your bonus balance: a friend you invited made their first deposit."))
    return cents


def reverse_referral_bonus(order) -> int:
    """The deposit that earned a referral bonus was refunded: take the bonus back (recorded even if already spent)."""
    ref = Referral.query.filter_by(qualifying_order_id=order.id).first() if order is not None else None
    if ref is None or not ref.reward_cents or ref.status == "reversed":
        return 0
    if ledger.debit(ref.referrer_id, ref.reward_cents, "referral_bonus_reversal", "referral", ref.id, allow_negative=True, bucket="bonus"):
        ref.status = "reversed"
        return ref.reward_cents
    return 0


def reverse_deposit_bonus(order, refunded_cents: int, paid_cents: int):
    """A refunded deposit takes back its proportional share of the bonus (recorded even if already spent)."""
    if not order.bonus_cents or paid_cents <= 0:
        return 0
    share = min(order.bonus_cents, (order.bonus_cents * refunded_cents + paid_cents // 2) // paid_cents)
    if share > 0 and ledger.debit(order.player_id, share, "deposit_bonus_reversal", "payment_order", order.id,
                                  allow_negative=True, bucket="bonus"):
        return share
    return 0


def apply_box_reward(player_id, reward, box):
    """Apply a freshly opened box's reward immediately. Returns a player-facing note."""
    if box.prize_kind == "deposit_bonus_percent":
        boost = activate_boost(player_id, box.prize_percent, box.boost_hours)
        return f"Deposit Boost active: +{boost.percent}% bonus on every deposit for the next {box.boost_hours} hours."
    cents = box.prize_cents or 0
    ledger.credit(player_id, cents, "box_reward", "player_reward", reward.id, bucket="bonus")
    return f"${cents / 100:g} added to your bonus balance. Use it on any game with Add Cash."
