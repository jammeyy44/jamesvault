"""
Platform balances: integer-cents "wallet" (real money, withdrawable) and "bonus" (free play / bonus credit, spendable
on games only) on the player row, plus one append-only ledger for both.

Every change is an atomic conditional UPDATE plus a WalletEntry row in the caller's transaction. The ledger's
unique (kind, ref_type, ref_id) makes credits/debits idempotent: replaying a webhook or retrying a request can
never apply the same movement twice. The caller commits (and handles IntegrityError from a concurrent duplicate).
"""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import update

from app import db
from app.models_site import Player, WalletEntry

BUCKETS = {"wallet": Player.wallet_cents, "bonus": Player.bonus_cents}


class InsufficientFunds(Exception):
    pass


def to_cents(amount) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fmt(cents: int) -> str:
    return f"{(Decimal(cents) / 100).quantize(Decimal('0.01'))}"


def percent_of(cents: int, percent: int) -> int:
    """Integer rounding-half-up of cents*percent/100 (the browser preview uses the same formula)."""
    return (cents * percent + 50) // 100


def balance_cents(player_id: int, bucket: str = "wallet") -> int:
    return db.session.query(BUCKETS[bucket]).filter(Player.id == player_id).scalar() or 0


def _exists(kind, ref_type, ref_id):
    return WalletEntry.query.filter_by(kind=kind, ref_type=ref_type, ref_id=str(ref_id)).first() is not None


def _record(player_id, cents, kind, ref_type, ref_id, bucket):
    entry = WalletEntry(player_id=player_id, kind=kind, amount_cents=cents, ref_type=ref_type, ref_id=str(ref_id), bucket=bucket)
    db.session.add(entry)
    db.session.flush()
    entry.balance_after_cents = balance_cents(player_id, bucket)


def debit_exists(kind, ref_type, ref_id) -> bool:
    return _exists(kind, ref_type, ref_id)


def credit(player_id, cents, kind, ref_type, ref_id, bucket="wallet") -> bool:
    """Add funds. Returns False (and changes nothing) if this exact movement was already applied."""
    if cents <= 0:
        raise ValueError("credit must be positive")
    if _exists(kind, ref_type, ref_id):
        return False
    col = BUCKETS[bucket]
    db.session.execute(update(Player).where(Player.id == player_id).values({col: col + cents}))
    _record(player_id, cents, kind, ref_type, ref_id, bucket)
    return True


def debit(player_id, cents, kind, ref_type, ref_id, allow_negative=False, bucket="wallet") -> bool:
    """Remove funds atomically. Raises InsufficientFunds unless allow_negative (used only for provider refunds,
    which must be recorded even if the player already spent the money)."""
    if cents <= 0:
        raise ValueError("debit must be positive")
    if _exists(kind, ref_type, ref_id):
        return False
    col = BUCKETS[bucket]
    stmt = update(Player).where(Player.id == player_id).values({col: col - cents})
    if not allow_negative:
        stmt = stmt.where(col >= cents)  # compare-and-set: two racing debits cannot both succeed
    if db.session.execute(stmt).rowcount != 1:
        raise InsufficientFunds()
    _record(player_id, -cents, kind, ref_type, ref_id, bucket)
    return True
