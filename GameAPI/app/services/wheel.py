"""
Free-spin wheel: unlocked by a confirmed deposit, one spin per 24 hours, prize chosen on the server and applied instantly.

Eligible  = a wallet deposit credited in the last 24h (and not refunded).
Can spin  = eligible AND no spin in the last 24h.
Applying  = diamonds -> diamond balance, freeplay -> bonus balance, boost_percent -> Deposit Boost. All idempotent ledger movements.
"""
import secrets
from datetime import timedelta

from app import db
from app.models_site import WalletEntry, WheelPrize, WheelSpin
from app.services import bonus, wallet as ledger
from app.utils.auth import utcnow

WINDOW = timedelta(hours=24)

DEFAULT_PRIZES = [
    # kind, value, weight, boost_hours
    ("diamonds", 1, 30, 24), ("diamonds", 2, 22, 24), ("diamonds", 4, 12, 24),
    ("freeplay", 200, 14, 24), ("freeplay", 300, 8, 24), ("freeplay", 500, 3, 24),
    ("boost_percent", 5, 11, 24),
]


def ensure_default_prizes():
    """Seed once. Prizes left over from the previous (staff-fulfilled) wheel have no kind/value: switch them off."""
    WheelPrize.query.filter(WheelPrize.value <= 0).update({"is_active": False}, synchronize_session=False)
    if WheelPrize.query.count() == 0:
        for kind, value, weight, hours in DEFAULT_PRIZES:
            prize = WheelPrize(kind=kind, value=value, weight=weight, boost_hours=hours, label="")
            prize.label = f"{prize.title} {prize.subtitle}"
            db.session.add(prize)


def active_prizes():
    return WheelPrize.query.filter(WheelPrize.is_active.is_(True), WheelPrize.value > 0, WheelPrize.weight > 0).order_by(WheelPrize.id).all()


def qualifying_deposit(player_id, now=None):
    """The latest deposit credited within 24h that has not been refunded (or None)."""
    now = now or utcnow()
    refunded = db.session.query(WalletEntry.ref_id).filter(WalletEntry.kind == "refund", WalletEntry.ref_type == "payment_order")
    q = WalletEntry.query.filter(
        WalletEntry.player_id == player_id, WalletEntry.kind == "deposit", WalletEntry.created_at >= now - WINDOW,
        db.or_(WalletEntry.ref_type != "payment_order", ~WalletEntry.ref_id.in_(refunded)))
    return q.order_by(WalletEntry.created_at.desc(), WalletEntry.id.desc()).first()


def last_spin(player_id):
    return WheelSpin.query.filter_by(player_id=player_id).order_by(WheelSpin.created_at.desc(), WheelSpin.id.desc()).first()


def state(player_id, now=None):
    now = now or utcnow()
    dep, spin = qualifying_deposit(player_id, now), last_spin(player_id)
    spun_recently = spin is not None and spin.created_at > now - WINDOW
    can_spin = dep is not None and not spun_recently
    out = {"eligible": dep is not None, "can_spin": can_spin, "closes_in": None, "next_spin_in": None, "deposit_id": dep.id if dep else None}
    if can_spin:
        out["closes_in"] = max(0, int((dep.created_at + WINDOW - now).total_seconds()))  # time left to use this unlock
    elif spun_recently:
        out["next_spin_in"] = max(0, int((spin.created_at + WINDOW - now).total_seconds()))
    return out


def pick(prizes):
    """Weighted choice from a CSPRNG. The browser never influences the outcome."""
    total = sum(p.weight for p in prizes)
    roll = secrets.SystemRandom().uniform(0, total)
    acc = 0
    for p in prizes:
        acc += p.weight
        if roll <= acc:
            return p
    return prizes[-1]


def apply_prize(player_id, prize, spin):
    """Apply immediately inside the caller's transaction. Returns a player-facing note."""
    if prize.kind == "diamonds":
        bonus.credit_diamonds(player_id, prize.value, "wheel", "wheel_spin", spin.id)
        return f"{prize.value} diamond{'s' if prize.value != 1 else ''} added to your balance."
    if prize.kind == "freeplay":
        ledger.credit(player_id, prize.value, "wheel_reward", "wheel_spin", spin.id, bucket="bonus")
        return f"${prize.value / 100:g} free play added to your bonus balance. Use it on any game with Add Cash."
    boost = bonus.activate_boost(player_id, prize.value, prize.boost_hours)
    return f"Deposit Boost active: +{boost.percent}% bonus on every deposit for the next {prize.boost_hours} hours."
