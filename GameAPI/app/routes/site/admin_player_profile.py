"""Admin: everything about one player on a single screen (support + superadmin). Read-only.

Never returns passwords, game login passwords, payout addresses or tokens."""
from decimal import Decimal

from flask import jsonify
from sqlalchemy import func

from app import db
from app.models_site import (
    CashRequest, Coupon, CouponRedemption, GameAccount, PaymentOrder, Player, Referral, RedeemRequest, WithdrawalOrder, iso,
)
from app.services import wallet as ledger
from app.utils.auth import admin_required, json_error

from . import site_bp

A = '/admin'
LIMIT = 100


def _money(cents):
    return ledger.fmt(cents or 0)


def _dec(value):
    return f"{Decimal(value or 0):.2f}"


@site_bp.route(f'{A}/players/<int:pid>/profile')
@admin_required('support')
def admin_player_profile(pid):
    p = db.session.get(Player, pid)
    if not p:
        return json_error("Not found", 404)

    accounts = GameAccount.query.filter_by(player_id=pid).order_by(GameAccount.id).all()
    cash = CashRequest.query.filter_by(player_id=pid).order_by(CashRequest.id.desc()).limit(LIMIT).all()
    redeems = RedeemRequest.query.filter_by(player_id=pid).order_by(RedeemRequest.id.desc()).limit(LIMIT).all()
    deposits = PaymentOrder.query.filter_by(player_id=pid).order_by(PaymentOrder.id.desc()).limit(LIMIT).all()
    withdrawals = WithdrawalOrder.query.filter_by(player_id=pid).order_by(WithdrawalOrder.id.desc()).limit(LIMIT).all()
    coupons = (db.session.query(CouponRedemption, Coupon).join(Coupon, Coupon.id == CouponRedemption.coupon_id)
               .filter(CouponRedemption.player_id == pid).order_by(CouponRedemption.id.desc()).limit(LIMIT).all())
    referred = Referral.query.filter_by(referrer_id=pid).order_by(Referral.id.desc()).limit(LIMIT).all()
    referred_by = Referral.query.filter_by(referred_id=pid).first()
    referrer = db.session.get(Player, referred_by.referrer_id) if referred_by else None

    # per game: what was added, what bonus came with it, what was cashed out
    per_game = []
    for a in accounts:
        ok = [c for c in cash if c.game_account_id == a.id and c.status in ('completed', 'needs_review', 'processing')]
        done_redeems = [r for r in redeems if r.game_account_id == a.id and r.status == 'completed']
        per_game.append({
            "game": a.game.name, "slug": a.game.slug, "login_username": a.provider_username, "status": a.status,
            "sandbox": a.sandbox, "login_created_at": iso(a.created_at),
            "cash_added": _dec(sum((c.amount for c in ok), Decimal("0"))),
            "bonus_added": _dec(sum((c.bonus_amount or 0 for c in ok), Decimal("0"))),
            "adds": len(ok),
            "cashed_out": _money(sum(r.payout_cents for r in done_redeems)),
            "cashouts": len(done_redeems),
        })

    signup = next((c for c in reversed(cash) if c.bonus_kind == 'signup' and c.status in ('completed', 'needs_review', 'processing')), None)
    paid_deposits = sum(d.amount_cents for d in deposits if d.status == 'paid')
    withdrawn = sum(w.amount_cents for w in withdrawals if w.status in ('completed', 'submitted', 'sending', 'pending_review'))

    return jsonify({
        "player": {
            **p.to_dict(), "wallet": _money(p.wallet_cents), "bonus_balance": _money(p.bonus_cents), "diamonds": p.diamonds,
            "last_login_at": iso(p.last_login_at), "referral_code": p.referral_code,
            "referred_by": referrer.username if referrer else None,
        },
        "signup_bonus": {
            "email_verified": bool(p.email_verified), "claimed": p.signup_bonus_claimed_at is not None,
            "claimed_at": iso(p.signup_bonus_claimed_at),
            "game": signup.account.game.name if signup else None,
            "cash_added": _dec(signup.amount) if signup else None,
            "bonus_amount": _dec(signup.bonus_amount) if signup else None,
        },
        "totals": {
            "deposited": _money(paid_deposits),
            "cash_added_to_games": _dec(sum((c.amount for c in cash if c.status == 'completed'), Decimal("0"))),
            "game_bonus_received": _dec(sum((c.bonus_amount or 0 for c in cash if c.status == 'completed'), Decimal("0"))),
            "redeemed_to_wallet": _money(sum(r.payout_cents for r in redeems if r.status == 'completed')),
            "withdrawals_requested": _money(withdrawn),
            "coupon_total": _money(sum(r.amount_cents for r, _ in coupons)),
            "referral_earned": _money(sum(r.reward_cents or 0 for r in referred)),
        },
        "games": per_game,
        "cash_adds": [{"id": c.id, "game": c.account.game.name, "amount": _dec(c.amount), "bonus": _dec(c.bonus_amount),
                       "bonus_kind": c.bonus_kind, "source": c.source, "status": c.status, "at": iso(c.created_at)} for c in cash],
        "deposits": [{"id": d.id, "amount": _money(d.amount_cents), "method": d.method_name, "status": d.status,
                      "bonus": _money(d.bonus_cents) if d.bonus_cents else None, "at": iso(d.created_at)} for d in deposits],
        "redeems": [{"id": r.id, "game": r.account.game.name, "game_balance": _money(r.balance_cents), "payout": _money(r.payout_cents),
                     "voided": _money(r.void_cents), "status": r.status, "at": iso(r.created_at)} for r in redeems],
        "withdrawals": [{"id": w.id, "amount": _money(w.amount_cents), "method": w.method_name, "status": w.status,
                         "at": iso(w.created_at)} for w in withdrawals],
        "coupons": [{"code": c.code, "amount": _money(r.amount_cents), "at": iso(r.created_at)} for r, c in coupons],
        "referrals": [{"username": r.referred.username if r.referred else "?", "status": r.status,
                       "reward": _money(r.reward_cents) if r.reward_cents else None, "at": iso(r.created_at)} for r in referred],
    })
