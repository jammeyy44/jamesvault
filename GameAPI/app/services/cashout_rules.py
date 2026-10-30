"""
Cashout (redeem) rules: how much of a game's winnings a player may redeem, decided by their most recent deposit.

    DEPOSIT      MINIMUM   MAXIMUM
    $5           $50       $50
    $5 - $9      $50       $100
    $10 - $16    $50       x12
    $17 - $25    x3        x12
    $26 - $30    x3        x12
    $30+         x3        x12 (max $500)

"x3" / "x12" mean 3x / 12x the deposit. Winnings above the maximum are voided by the system.

Band edges (all in integer cents, no floating point):
    exactly $5.00 | above $5 up to $9.99 | $10.00-$16.99 | $17.00-$25.99 | $26.00-$30.00 | above $30
A deposit under $5 has no row (deposits under $5 are not accepted). The $500 cap applies from the $26 row on (it cannot
bite earlier: 12 x $30 = $360). When 3x the deposit would exceed the cap (deposits over ~$166.67) the minimum is clamped to
the maximum so the range is never empty.
"""
from app import db
from app.models_site import WalletEntry

CAP_CENTS = 50_000

# What players see (same wording as the rule sheet).
TABLE = [
    {"deposit": "$5", "min": "$50", "max": "$50"},
    {"deposit": "$5 - $9", "min": "$50", "max": "$100"},
    {"deposit": "$10 - $16", "min": "$50", "max": "x12"},
    {"deposit": "$17 - $25", "min": "x3", "max": "x12"},
    {"deposit": "$26 - $30", "min": "x3", "max": "x12"},
    {"deposit": "$30+", "min": "x3", "max": "x12 (max $500)"},
]
NOTE = "Winning amount above the maximum is voided by the system."


def row_index(deposit_cents: int):
    d = deposit_cents
    if d < 500:
        return None
    if d == 500:
        return 0
    if d < 1000:
        return 1
    if d < 1700:
        return 2
    if d < 2600:
        return 3
    if d <= 3000:
        return 4
    return 5


def limits(deposit_cents: int):
    """{row, deposit_cents, min_cents, max_cents} for a deposit, or None if it does not qualify."""
    row = row_index(deposit_cents)
    if row is None:
        return None
    d = deposit_cents
    lo, hi = {
        0: (5000, 5000),
        1: (5000, 10000),
        2: (5000, 12 * d),
        3: (3 * d, 12 * d),
        4: (3 * d, 12 * d),
        5: (3 * d, min(12 * d, CAP_CENTS)),
    }[row]
    return {"row": row, "deposit_cents": d, "min_cents": min(lo, hi), "max_cents": hi}


def outcome(balance_cents: int, rule: dict):
    """What redeeming a game balance does: (payout, voided). Below the minimum nothing can be redeemed."""
    if balance_cents < rule["min_cents"]:
        return 0, 0
    payout = min(balance_cents, rule["max_cents"])
    return payout, balance_cents - payout


def latest_deposit(player_id):
    """The player's most recent confirmed wallet deposit that was not refunded (all-time), or None."""
    refunded = db.session.query(WalletEntry.ref_id).filter(WalletEntry.kind == "refund", WalletEntry.ref_type == "payment_order")
    return (WalletEntry.query.filter(
        WalletEntry.player_id == player_id, WalletEntry.kind == "deposit",
        db.or_(WalletEntry.ref_type != "payment_order", ~WalletEntry.ref_id.in_(refunded)))
        .order_by(WalletEntry.created_at.desc(), WalletEntry.id.desc()).first())


class GameDepositRecord:
    def __init__(self, obj_id, amount_cents, created_at):
        self.id = obj_id
        self.amount_cents = amount_cents
        self.created_at = created_at


def latest_game_deposit(player_id, game_account_id=None):
    """The player's most recent deposit INTO THE GAME (CashRequest), or fallback to wallet deposit."""
    from app.models_site import CashRequest
    from app.services import wallet as ledger
    
    q = CashRequest.query.filter_by(player_id=player_id, status='completed')
    if game_account_id is not None:
        q = q.filter_by(game_account_id=game_account_id)
    req = q.order_by(CashRequest.processed_at.desc(), CashRequest.id.desc()).first()
    if req:
        return GameDepositRecord(req.id, ledger.to_cents(req.amount), req.created_at)
        
    if game_account_id is not None:
        req_any = CashRequest.query.filter_by(player_id=player_id, status='completed').order_by(CashRequest.processed_at.desc(), CashRequest.id.desc()).first()
        if req_any:
            return GameDepositRecord(req_any.id, ledger.to_cents(req_any.amount), req_any.created_at)
            
    w_dep = latest_deposit(player_id)
    if w_dep:
        return GameDepositRecord(w_dep.id, w_dep.amount_cents, w_dep.created_at)
    return None

