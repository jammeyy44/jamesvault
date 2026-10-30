"""
Models for the JamesVault player-facing site: players, catalog, promotions,
referrals, tournaments, support and audit records.

All timestamps are naive UTC. Monetary values use Numeric; nothing here credits money automatically.
"""
import secrets

from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.utils.auth import utcnow
from app.utils.crypto import EncryptedText


def new_referral_code():
    return secrets.token_hex(4).upper()


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')  # active | suspended
    # player | support | content | superadmin. Set only by seed_site.py (ADMIN_EMAILS) or a superadmin, never at signup.
    role = db.Column(db.String(20), nullable=False, default='player', server_default='player')
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    # Platform wallet balance in integer cents (exact). Always changed with an atomic conditional UPDATE together
    # with a WalletEntry row, so it can be reconciled against the ledger.
    wallet_cents = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    # Bonus balance in integer cents: free play / bonus credit. Spendable only on games (Add Cash), never withdrawable.
    bonus_cents = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    # Bonus Zone diamonds (integer). Same atomic-update + ledger pattern as the wallet.
    diamonds = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    referral_code = db.Column(db.String(16), unique=True, nullable=False, default=new_referral_code)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id, "username": self.username, "email": self.email,
            "status": self.status, "role": self.role, "is_admin": self.role != 'player',
            "email_verified": self.email_verified, "referral_code": self.referral_code, "created_at": iso(self.created_at),
        }


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)  # sha256 of the emailed token
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    purpose = db.Column(db.String(12), nullable=False, default='reset', server_default='reset')  # reset | verify_email
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class CatalogGame(db.Model):
    """Admin-managed catalog entry. launch_supported stays False until a provider launch contract exists."""
    __tablename__ = 'catalog_games'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=True)
    category = db.Column(db.String(40), nullable=False, default='general')
    image_url = db.Column(db.String(500), nullable=True)
    download_url = db.Column(db.String(500), nullable=True)  # where players get the game app (shown as the download button)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active')  # active | maintenance | hidden
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    is_new = db.Column(db.Boolean, nullable=False, default=False)
    launch_supported = db.Column(db.Boolean, nullable=False, default=False)
    cashout_min = db.Column(db.Numeric(12, 2), nullable=True)  # shown to players only when an admin sets it
    cashout_max = db.Column(db.Numeric(12, 2), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    provider = db.relationship('Provider', lazy='joined')

    def to_dict(self):
        return {
            "id": self.id, "slug": self.slug, "name": self.name,
            "provider": self.provider.name if self.provider else None,
            "provider_id": self.provider_id, "category": self.category,
            "image_url": self.image_url, "download_url": self.download_url, "description": self.description,
            "status": self.status, "is_featured": self.is_featured, "is_new": self.is_new,
            "launch_supported": self.launch_supported, "sort_order": self.sort_order,
            "cashout_min": str(self.cashout_min) if self.cashout_min is not None else None,
            "cashout_max": str(self.cashout_max) if self.cashout_max is not None else None,
        }


class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = (db.UniqueConstraint('player_id', 'game_id', name='uq_favorite'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('catalog_games.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Promotion(db.Model):
    __tablename__ = 'promotions'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    # welcome | first_deposit | deposit_match | free_play | free_spins | daily | referral | seasonal | coupon
    promo_type = db.Column(db.String(30), nullable=False, default='seasonal')
    description = db.Column(db.Text, nullable=True)
    eligibility = db.Column(db.Text, nullable=True)
    reward_details = db.Column(db.Text, nullable=True)
    terms = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    # Claim rule enforced by the API: open | new_player | coupon. Deposit-based rules are not claimable yet.
    claim_rule = db.Column(db.String(20), nullable=False, default='open')
    new_player_days = db.Column(db.Integer, nullable=False, default=7)
    coupon_code = db.Column(db.String(40), nullable=True)
    repeat = db.Column(db.String(10), nullable=False, default='once')  # once | daily
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def window_state(self, now=None):
        now = now or utcnow()
        if not self.is_active:
            return 'disabled'
        if self.starts_at and now < self.starts_at:
            return 'scheduled'
        if self.ends_at and now > self.ends_at:
            return 'ended'
        return 'live'

    def to_dict(self, public=True):
        d = {
            "id": self.id, "slug": self.slug, "title": self.title, "promo_type": self.promo_type,
            "description": self.description, "eligibility": self.eligibility,
            "reward_details": self.reward_details, "terms": self.terms, "image_url": self.image_url,
            "claim_rule": self.claim_rule, "repeat": self.repeat,
            "starts_at": iso(self.starts_at), "ends_at": iso(self.ends_at), "state": self.window_state(),
        }
        if not public:
            d.update(is_active=self.is_active, coupon_code=self.coupon_code, new_player_days=self.new_player_days)
        return d


class PromotionClaim(db.Model):
    """A claim request. Fulfilment is manual (admin) until a verified credit mechanism exists."""
    __tablename__ = 'promotion_claims'

    id = db.Column(db.Integer, primary_key=True)
    promotion_id = db.Column(db.Integer, db.ForeignKey('promotions.id'), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    # once: "<promo>:<player>"; daily: "<promo>:<player>:<YYYY-MM-DD>". Uniqueness blocks double claims and races.
    claim_key = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | fulfilled | rejected
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    promotion = db.relationship('Promotion', lazy='joined')


class WheelPrize(db.Model):
    """A slice of the free-spin wheel. Odds = weight / sum(active weights), and are shown to players."""
    __tablename__ = 'wheel_prizes'

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    weight = db.Column(db.Integer, nullable=False, default=1)
    kind = db.Column(db.String(16), nullable=False, default='diamonds', server_default='diamonds')  # diamonds | freeplay | boost_percent
    value = db.Column(db.Integer, nullable=False, default=0, server_default='0')  # diamonds: count, freeplay: cents, boost_percent: percent
    boost_hours = db.Column(db.Integer, nullable=False, default=24, server_default='24')
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def title(self):
        if self.kind == 'freeplay':
            return f"${self.value / 100:g}"
        if self.kind == 'boost_percent':
            return f"{self.value}%"
        return str(self.value)

    @property
    def subtitle(self):
        if self.kind == 'freeplay':
            return "Freeplay"
        if self.kind == 'boost_percent':
            return "Deposit boost"
        return "Diamond" if self.value == 1 else "Diamonds"

    def to_dict(self):
        return {"id": self.id, "label": self.label, "kind": self.kind, "value": self.value, "title": self.title,
                "subtitle": self.subtitle, "weight": self.weight, "boost_hours": self.boost_hours, "is_active": self.is_active}


class WheelSpin(db.Model):
    __tablename__ = 'wheel_spins'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    spin_key = db.Column(db.String(60), unique=True, nullable=False)  # "<player>:dep<deposit ledger id>": one spin per deposit
    prize_id = db.Column(db.Integer, db.ForeignKey('wheel_prizes.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='applied')  # applied instantly (legacy: pending | fulfilled)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    prize = db.relationship('WheelPrize', lazy='joined')


class Referral(db.Model):
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey('players.id'), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | confirmed | rejected
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    referred = db.relationship('Player', foreign_keys=[referred_id], lazy='joined')


class Tournament(db.Model):
    __tablename__ = 'tournaments'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    rules = db.Column(db.Text, nullable=True)
    entry_conditions = db.Column(db.Text, nullable=True)
    prize_info = db.Column(db.Text, nullable=True)  # verified prize text entered by an admin
    image_url = db.Column(db.String(500), nullable=True)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def phase(self, now=None):
        now = now or utcnow()
        if now < self.starts_at:
            return 'upcoming'
        if now > self.ends_at:
            return 'completed'
        return 'active'

    def to_dict(self, public=True):
        d = {
            "id": self.id, "slug": self.slug, "title": self.title, "description": self.description,
            "rules": self.rules, "entry_conditions": self.entry_conditions, "prize_info": self.prize_info,
            "image_url": self.image_url, "starts_at": iso(self.starts_at), "ends_at": iso(self.ends_at),
            "phase": self.phase(),
        }
        if not public:
            d["is_active"] = self.is_active
        return d


class TournamentEntry(db.Model):
    __tablename__ = 'tournament_entries'
    __table_args__ = (db.UniqueConstraint('tournament_id', 'player_id', name='uq_tournament_entry'),)

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id'), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    score = db.Column(db.Numeric(14, 2), nullable=False, default=0)  # set by admins from verified results only
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    player = db.relationship('Player', lazy='joined')


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True, index=True)
    contact_email = db.Column(db.String(254), nullable=True)
    subject = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')  # open | answered | closed
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    messages = db.relationship('TicketMessage', backref='ticket', order_by='TicketMessage.id', lazy='select')


class TicketMessage(db.Model):
    __tablename__ = 'ticket_messages'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False, index=True)
    author_type = db.Column(db.String(10), nullable=False)  # player | staff
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_type = db.Column(db.String(12), nullable=False)  # admin | player | anonymous | system
    actor_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    target = db.Column(db.String(120), nullable=True)
    detail = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class GameAccount(db.Model):
    """A player's login on a game provider. The password is stored encrypted (players can view it again)."""
    __tablename__ = 'game_accounts'
    __table_args__ = (db.UniqueConstraint('player_id', 'game_id', name='uq_game_account'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('catalog_games.id'), nullable=False)
    provider_username = db.Column(db.String(60), nullable=False)
    provider_user_id = db.Column(db.String(40), nullable=True)  # the provider's own player id (agent API panels), when it told us
    password_enc = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | active
    sandbox = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    game = db.relationship('CatalogGame', lazy='joined')


class CashRequest(db.Model):
    """A request to add credit to a game account. Credit is applied only after payment is confirmed
    (sandbox: instantly, clearly flagged; live: staff confirm, then the provider recharge runs exactly once)."""
    __tablename__ = 'cash_requests'
    __table_args__ = (db.UniqueConstraint('player_id', 'idempotency_key', name='uq_cash_idem'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    game_account_id = db.Column(db.Integer, db.ForeignKey('game_accounts.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    source = db.Column(db.String(8), nullable=False, default='wallet', server_default='wallet')  # wallet | bonus
    idempotency_key = db.Column(db.String(64), nullable=False)
    # awaiting_staff -> processing -> completed | failed | needs_review (ambiguous provider outcome: reconcile by hand)
    # or awaiting_staff -> rejected
    status = db.Column(db.String(20), nullable=False, default='awaiting_staff')
    sandbox = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    account = db.relationship('GameAccount', lazy='joined')


class ProviderLog(db.Model):
    """One row per call made to a provider panel (no credentials or request bodies are stored)."""
    __tablename__ = 'provider_logs'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=True, index=True)
    action = db.Column(db.String(40), nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    detail = db.Column(db.String(240), nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class WalletEntry(db.Model):
    """Append-only ledger. The unique (kind, ref_type, ref_id) makes every credit/debit idempotent."""
    __tablename__ = 'wallet_entries'
    __table_args__ = (db.UniqueConstraint('kind', 'ref_type', 'ref_id', name='uq_wallet_ref'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    kind = db.Column(db.String(24), nullable=False)  # deposit | refund | withdrawal | withdrawal_refund | cash_to_game | cash_refund | adjustment
    amount_cents = db.Column(db.Integer, nullable=False)  # signed: + credit, - debit
    bucket = db.Column(db.String(8), nullable=False, default='wallet', server_default='wallet')  # wallet | bonus
    ref_type = db.Column(db.String(30), nullable=False)
    ref_id = db.Column(db.String(60), nullable=False)
    balance_after_cents = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PaymentOrder(db.Model):
    """A deposit (pay-in) order created at the payment provider. Credited to the wallet only after a verified paid event."""
    __tablename__ = 'payment_orders'
    __table_args__ = (db.UniqueConstraint('player_id', 'idempotency_key', name='uq_payment_idem'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    method_id = db.Column(db.String(40), nullable=False)
    method_value = db.Column(db.String(30), nullable=False)
    method_name = db.Column(db.String(60), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | paid | failed | refunded
    provider_deposit_id = db.Column(db.String(40), unique=True, nullable=True)
    reference_id = db.Column(db.String(40), nullable=True)
    payment_url = db.Column(db.String(500), nullable=True)
    # Deposit Boost active when the order was created (snapshot) and the bonus actually granted when it was paid.
    bonus_percent = db.Column(db.Integer, nullable=True)
    bonus_cents = db.Column(db.Integer, nullable=True)
    idempotency_key = db.Column(db.String(64), nullable=False)
    sandbox = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)


class WithdrawalOrder(db.Model):
    """A cashout. Funds are held (debited) at request time; a superadmin approves; the provider pays out once."""
    __tablename__ = 'withdrawal_orders'
    __table_args__ = (db.UniqueConstraint('player_id', 'idempotency_key', name='uq_withdrawal_idem'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    method_id = db.Column(db.String(40), nullable=False)
    method_value = db.Column(db.String(30), nullable=False)
    method_name = db.Column(db.String(60), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    address_enc = db.Column(EncryptedText, nullable=False)  # payout destination, encrypted at rest
    chime_name = db.Column(db.String(200), nullable=True)
    # pending_review -> sending -> submitted -> completed | cancelled | failed_at_provider ; or rejected | cancelled(by player)
    # needs_review (ambiguous send) | credited_back (staff returned funds after failed_at_provider)
    status = db.Column(db.String(24), nullable=False, default='pending_review')
    provider_withdrawal_id = db.Column(db.String(40), unique=True, nullable=True)
    reference_id = db.Column(db.String(40), nullable=True)
    note = db.Column(db.String(300), nullable=True)
    idempotency_key = db.Column(db.String(64), nullable=False)
    sandbox = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)


class WebhookDelivery(db.Model):
    """Every payment notification received (deduplicated on the provider's deliveryId)."""
    __tablename__ = 'webhook_deliveries'

    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.String(60), unique=True, nullable=False)
    event = db.Column(db.String(40), nullable=False)
    handled = db.Column(db.Boolean, nullable=False, default=False)  # False = needs staff attention (e.g. unmatched payment)
    credited = db.Column(db.Boolean, nullable=False, default=False)
    summary = db.Column(db.String(400), nullable=True)  # e.g. "depositId=..., amount=25.00, memo=<escaped by clients>"
    external_id = db.Column(db.String(40), nullable=True, index=True)
    amount_cents = db.Column(db.Integer, nullable=True)
    memo = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PaymentMethodSetting(db.Model):
    """Admin presentation of a provider payment method. Badges ("No fee", "+15%") are admin-entered text only."""
    __tablename__ = 'payment_method_settings'

    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(30), unique=True, nullable=False)  # provider's method value: cashapp, chime, ...
    label = db.Column(db.String(60), nullable=True)
    badge = db.Column(db.String(30), nullable=True)
    badge_tone = db.Column(db.String(10), nullable=False, default='green')  # green | amber | red | blue
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {"id": self.id, "value": self.value, "label": self.label, "badge": self.badge,
                "badge_tone": self.badge_tone, "is_enabled": self.is_enabled, "sort_order": self.sort_order}


class BonusTask(db.Model):
    """A diamond-earning task. The verification logic lives in code (app/services/bonus.py); admins edit reward/visibility."""
    __tablename__ = 'bonus_tasks'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(240), nullable=True)
    group = db.Column(db.String(10), nullable=False, default='general')  # general | daily | streak
    kind = db.Column(db.String(14), nullable=False, default='one_time')  # one_time | daily | weekly | per_referral
    reward_diamonds = db.Column(db.Integer, nullable=False, default=1)
    icon = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {"id": self.id, "key": self.key, "title": self.title, "description": self.description,
                "group": self.group, "kind": self.kind, "reward_diamonds": self.reward_diamonds, "icon": self.icon,
                "is_active": self.is_active, "sort_order": self.sort_order}


class TaskClaim(db.Model):
    """One row per completed task period. The unique claim_key blocks double claims, even under races."""
    __tablename__ = 'task_claims'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    task_key = db.Column(db.String(40), nullable=False)
    claim_key = db.Column(db.String(80), unique=True, nullable=False)
    diamonds = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class DiamondEntry(db.Model):
    __tablename__ = 'diamond_entries'
    __table_args__ = (db.UniqueConstraint('kind', 'ref_type', 'ref_id', name='uq_diamond_ref'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)  # signed
    kind = db.Column(db.String(16), nullable=False)  # task | box | adjustment
    ref_type = db.Column(db.String(30), nullable=False)
    ref_id = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class BonusBox(db.Model):
    """A Lucky Shop box. Each holds exactly one fixed, disclosed reward (no random draw)."""
    __tablename__ = 'bonus_boxes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    tone = db.Column(db.String(12), nullable=False, default='gift')  # gift | crystal | gold | ember | emerald (artwork)
    description = db.Column(db.String(160), nullable=True)
    cost_diamonds = db.Column(db.Integer, nullable=False, default=5)
    prize_kind = db.Column(db.String(24), nullable=False, default='freeplay')  # freeplay | deposit_bonus_percent | bonus_cash
    prize_cents = db.Column(db.Integer, nullable=True)
    prize_percent = db.Column(db.Integer, nullable=True)
    boost_hours = db.Column(db.Integer, nullable=False, default=24, server_default='24')  # how long a % boost lasts
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    @property
    def prize_label(self):
        if self.prize_kind == 'deposit_bonus_percent':
            return f"{self.prize_percent}% Deposit Bonus"
        dollars = f"${(self.prize_cents or 0) / 100:g}"
        return f"{dollars} Free Play" if self.prize_kind == 'freeplay' else f"{dollars} Bonus"

    def to_dict(self, public=True):
        d = {"id": self.id, "name": self.name, "tone": self.tone, "description": self.description,
             "cost_diamonds": self.cost_diamonds, "prize_kind": self.prize_kind, "prize_label": self.prize_label}
        if not public:
            d.update(prize_cents=self.prize_cents, prize_percent=self.prize_percent, boost_hours=self.boost_hours,
                     is_active=self.is_active, sort_order=self.sort_order)
        return d


class PlayerReward(db.Model):
    """What a player won from a box. A snapshot (label/value) so later edits never change past wins.
    Applied instantly when the box is opened: bonus balance credit, or a Deposit Boost."""
    __tablename__ = 'player_rewards'
    __table_args__ = (db.UniqueConstraint('player_id', 'open_key', name='uq_reward_open'),)

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    box_id = db.Column(db.Integer, db.ForeignKey('bonus_boxes.id'), nullable=True)
    box_name = db.Column(db.String(60), nullable=False)
    tone = db.Column(db.String(12), nullable=False)
    kind = db.Column(db.String(24), nullable=False)
    value_cents = db.Column(db.Integer, nullable=True)
    value_percent = db.Column(db.Integer, nullable=True)
    label = db.Column(db.String(60), nullable=False)
    cost_diamonds = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(12), nullable=False, default='applied')  # applied instantly (legacy: available | fulfilled | void)
    open_key = db.Column(db.String(64), nullable=False)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    fulfilled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {"id": self.id, "box": self.box_name, "tone": self.tone, "kind": self.kind, "label": self.label,
                "value_cents": self.value_cents, "value_percent": self.value_percent, "status": self.status,
                "note": self.note, "created_at": iso(self.created_at)}


class DepositBoost(db.Model):
    """A time-limited "+N% on all deposits" boost. One row per player; deposits made while it is active get the extra
    amount credited to the bonus balance."""
    __tablename__ = 'deposit_boosts'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), unique=True, nullable=False)
    percent = db.Column(db.Integer, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self, now=None):
        now = now or utcnow()
        return {"percent": self.percent, "expires_at": iso(self.expires_at),
                "seconds_left": max(0, int((self.expires_at - now).total_seconds()))}


class RedeemRequest(db.Model):
    """Taking winnings out of a game account. The player's latest deposit sets the min/max (app/services/cashout_rules.py);
    the payout goes to the wallet, anything above the maximum is voided. Taken out of the game FIRST, wallet credited after."""
    __tablename__ = 'redeem_requests'
    __table_args__ = (
        db.UniqueConstraint('player_id', 'idempotency_key', name='uq_redeem_idem'),
        db.UniqueConstraint('deposit_lock_id', name='uq_redeem_deposit'),  # one redeem per deposit; NULL when released
    )

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    game_account_id = db.Column(db.Integer, db.ForeignKey('game_accounts.id'), nullable=False, index=True)
    deposit_lock_id = db.Column(db.Integer, nullable=True)       # WalletEntry id of the deposit this redeem used
    deposit_cents = db.Column(db.Integer, nullable=False)
    min_cents = db.Column(db.Integer, nullable=False)            # rule snapshot
    max_cents = db.Column(db.Integer, nullable=False)
    balance_cents = db.Column(db.Integer, nullable=False)        # game balance taken out of the game
    payout_cents = db.Column(db.Integer, nullable=False)         # credited to the wallet
    void_cents = db.Column(db.Integer, nullable=False, default=0)  # above the maximum: voided
    status = db.Column(db.String(16), nullable=False, default='processing')  # processing | completed | failed | needs_review
    sandbox = db.Column(db.Boolean, nullable=False, default=False)
    idempotency_key = db.Column(db.String(64), nullable=False)
    note = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    account = db.relationship('GameAccount', lazy='joined')


class Coupon(db.Model):
    """A code an admin generates. It credits bonus cash instantly. Scope 'single': only the assigned account can use it
    (once). Scope 'many': any account can use it, but each account only once (optionally capped in total)."""
    __tablename__ = 'coupons'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)  # stored uppercase
    note = db.Column(db.String(120), nullable=True)
    reward_cents = db.Column(db.Integer, nullable=False)
    scope = db.Column(db.String(10), nullable=False, default='many')  # single | many
    assigned_player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)
    max_redemptions = db.Column(db.Integer, nullable=True)  # total cap for 'many'; NULL = unlimited
    redeemed_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self, assigned=None):
        return {
            "id": self.id, "code": self.code, "note": self.note, "amount": f"{self.reward_cents / 100:.2f}", "scope": self.scope,
            "assigned_to": assigned, "max_redemptions": self.max_redemptions, "redeemed_count": self.redeemed_count,
            "expires_at": iso(self.expires_at), "is_active": self.is_active, "created_at": iso(self.created_at),
        }


class CouponRedemption(db.Model):
    """One row per (coupon, account). The unique constraint is what makes 'once per account' impossible to bypass."""
    __tablename__ = 'coupon_redemptions'
    __table_args__ = (db.UniqueConstraint('coupon_id', 'player_id', name='uq_coupon_player'),)

    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False, index=True)
    amount_cents = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
