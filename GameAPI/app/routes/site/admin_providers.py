"""
Admin: provider management (agent-panel connections), provider call logs and cash-request reconciliation.

Adding a provider:
  1. Admin panel -> Providers -> New: name, adapter family (category), panel URL, agent username + password.
     The password is encrypted at rest and write-only: no endpoint ever returns it.
  2. Press "Test connection" (logs in, reads the agent balance).
  3. Assign games to it in Admin panel -> Game catalog (Provider field).
  A provider switched off receives no traffic; its games show as under maintenance.
A brand-new adapter family needs code: see ProviderGateway.SERVICES in app/services/gateway.py.
"""
import ipaddress
from urllib.parse import urlparse

from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Provider, RemoteProvider
from app.models_site import CashRequest, CatalogGame, Notification, Player, ProviderLog, iso
from app.utils.auth import admin_required, audit, json_error, utcnow

from . import site_bp

A = '/admin'


def _body():
    return request.get_json(silent=True) or {}


def _notify(pid, title, body=None):
    db.session.add(Notification(player_id=pid, title=title, body=body))


def _provider_view(p):
    d = p.to_dict()
    d["has_password"] = bool(p.password)  # write-only: the password itself is never returned
    d["games"] = CatalogGame.query.filter_by(provider_id=p.id).count()
    return d


def _valid_base_url(url):
    """http(s) only, no credentials in the URL, and never loopback/private/link-local (blocks SSRF into our network)."""
    try:
        u = urlparse(url)
    except ValueError:
        return False
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
        return False
    host = u.hostname.lower()
    if host == 'localhost' or host.endswith(('.local', '.internal')):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # a normal DNS name
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


@site_bp.route(f'{A}/providers')
@admin_required('support', 'content')
def admin_providers():
    from app.services.gateway import adapter_families
    rows = Provider.query.order_by(Provider.name).all()
    return jsonify({"items": [_provider_view(p) for p in rows],
                    "families": adapter_families([(p.category.name, p.name) for p in rows])})


@site_bp.route(f'{A}/providers', methods=['POST'])
@admin_required()
def admin_provider_create():
    d = _body()
    name, base_url = (d.get('name') or '').strip(), (d.get('base_url') or '').strip().rstrip('/')
    username, password = (d.get('username') or '').strip(), d.get('password') or ''
    if d.get('category') not in RemoteProvider.__members__:
        return json_error("Choose a valid adapter family (category).")
    if not name or not username or not password:
        return json_error("Name, username and password are required.")
    if not _valid_base_url(base_url):
        return json_error("Enter a public http(s) URL for the provider panel.")
    p = Provider(name=name, category=RemoteProvider[d['category']], base_url=base_url, username=username,
                 password=password, is_active=bool(d.get('is_active', True)))
    db.session.add(p)
    try:
        audit("provider.create", target=name)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("A provider with that name already exists.", 409)
    return jsonify(_provider_view(p)), 201


@site_bp.route(f'{A}/providers/<int:pid>', methods=['PATCH'])
@admin_required()
def admin_provider_update(pid):
    p = db.session.get(Provider, pid)
    if not p:
        return json_error("Not found", 404)
    d = _body()
    if (d.get('name') or '').strip():
        p.name = d['name'].strip()
    if 'category' in d:
        if d['category'] not in RemoteProvider.__members__:
            return json_error("Choose a valid adapter family (category).")
        p.category = RemoteProvider[d['category']]
    if 'base_url' in d:
        url = (d['base_url'] or '').strip().rstrip('/')
        if not _valid_base_url(url):
            return json_error("Enter a public http(s) URL for the provider panel.")
        p.base_url = url
    if (d.get('username') or '').strip():
        p.username = d['username'].strip()
    if d.get('password'):  # blank = keep the current password
        p.password = d['password']
    if 'is_active' in d:
        p.is_active = bool(d['is_active'])
    try:
        audit("provider.update", target=str(pid),
              detail={"fields": sorted(k for k in d if k != 'password'), "password_changed": bool(d.get('password'))})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("A provider with that name already exists.", 409)
    return jsonify(_provider_view(p))


@site_bp.route(f'{A}/providers/<int:pid>', methods=['DELETE'])
@admin_required()
def admin_provider_delete(pid):
    p = db.session.get(Provider, pid)
    if not p:
        return json_error("Not found", 404)
    if CatalogGame.query.filter_by(provider_id=pid).count():
        return json_error("This provider still has games assigned. Reassign them or switch the provider off instead.", 409)
    name = p.name
    db.session.delete(p)
    audit("provider.delete", target=name)
    db.session.commit()
    return jsonify({"ok": True})


@site_bp.route(f'{A}/providers/<int:pid>/test', methods=['POST'])
@admin_required()
def admin_provider_test(pid):
    """Log in to the provider panel and read the agent balance. Counts as a provider call (logged)."""
    from app.services.gateway import ProviderGateway
    p = db.session.get(Provider, pid)
    if not p:
        return json_error("Not found", 404)
    audit("provider.test", target=str(pid))
    db.session.commit()
    return jsonify(ProviderGateway().test_connection(p))


@site_bp.route(f'{A}/provider-logs')
@admin_required()
def admin_provider_logs():
    rows = ProviderLog.query.order_by(ProviderLog.id.desc()).limit(300).all()
    names = {p.id: p.name for p in Provider.query.all()}
    return jsonify({"items": [{"id": r.id, "provider": names.get(r.provider_id, "-"), "action": r.action,
                               "success": r.success, "detail": r.detail, "duration_ms": r.duration_ms,
                               "created_at": iso(r.created_at)} for r in rows]})


# ---------------------------------------------------------------- cash requests (money movement: superadmin only)
@site_bp.route(f'{A}/cash-requests')
@admin_required()
def admin_cash_requests():
    q = CashRequest.query
    if request.args.get('status'):
        q = q.filter(CashRequest.status.in_(request.args['status'].split(',')))
    rows = q.order_by(CashRequest.id.desc()).limit(200).all()
    names = {p.id: p.username for p in Player.query.filter(Player.id.in_({r.player_id for r in rows} or [0]))}
    return jsonify({"items": [{
        "id": r.id, "player": names.get(r.player_id), "game": r.account.game.name,
        "game_login": r.account.provider_username, "amount": f"{r.amount:.2f}", "status": r.status,
        "sandbox": r.sandbox, "note": r.note, "created_at": iso(r.created_at)} for r in rows]})


@site_bp.route(f'{A}/cash-requests/<int:rid>', methods=['PATCH'])
@admin_required()
def admin_cash_request_update(rid):
    """confirm: staff verified the payment -> run the provider recharge exactly once.
    reject: close an awaiting request.
    resolve_completed / resolve_failed: reconcile a needs_review request by hand after checking the provider panel
    (an ambiguous provider outcome is never retried automatically)."""
    from app.services.gateway import AmbiguousOutcome, GatewayError, get_gateway
    action = _body().get('action')
    req = db.session.get(CashRequest, rid)
    if not req or action not in ('confirm', 'reject', 'resolve_completed', 'resolve_failed'):
        return json_error("Invalid request")
    if req.sandbox:
        return json_error("Sandbox requests are already completed.", 409)

    if action.startswith('resolve_'):
        outcome = 'completed' if action == 'resolve_completed' else 'failed'
        n = (CashRequest.query.filter_by(id=rid, status='needs_review')
             .update({"status": outcome}, synchronize_session=False))
        db.session.commit()
        if n != 1:
            return json_error("Only requests needing review can be resolved.", 409)
        req = db.session.get(CashRequest, rid)
        req.processed_at, req.note = utcnow(), f"Reconciled by staff: {outcome}"
        if outcome == 'failed':  # wallet-funded requests held the money: return it (no-op for non-wallet requests)
            from app.services import wallet as ledger
            if ledger.debit_exists('cash_to_game', 'cash_request', req.id):
                ledger.credit(req.player_id, ledger.to_cents(req.amount), 'cash_refund', 'cash_request', req.id, bucket=req.source)
        _notify(req.player_id, f"Cash request {outcome}", f"${req.amount:.2f} for {req.account.game.name}")
        audit("cash.resolve", target=str(rid), detail={"result": outcome})
        db.session.commit()
        return jsonify({"status": outcome})

    target = 'processing' if action == 'confirm' else 'rejected'
    # Atomic claim: only one concurrent caller can move awaiting_staff -> processing/rejected.
    claimed = (CashRequest.query.filter_by(id=rid, status='awaiting_staff')
               .update({"status": target}, synchronize_session=False))
    db.session.commit()
    if claimed != 1:
        return json_error("This request has already been handled.", 409)
    req = db.session.get(CashRequest, rid)
    if action == 'reject':
        req.processed_at = utcnow()
        audit("cash.reject", target=str(rid))
        db.session.commit()
        return jsonify({"status": "rejected"})

    gateway = get_gateway()
    try:
        if gateway is None:
            raise GatewayError("Game accounts are disabled.")
        gateway.recharge(req.account, req.amount)
        req.status, req.note = 'completed', None
    except GatewayError as e:  # refused / unreachable before anything was applied: safe to fail
        req.status, req.note = 'failed', str(e)[:300]
    except Exception:  # AmbiguousOutcome or anything unexpected: the credit may have landed, so do NOT mark failed
        req.status = 'needs_review'
        req.note = "Provider outcome unknown. Check the provider panel, then resolve this request by hand."
    req.processed_at = utcnow()
    if req.status != 'needs_review':
        _notify(req.player_id, f"Cash request {req.status}", f"${req.amount:.2f} for {req.account.game.name}")
    audit("cash.confirm", target=str(rid), detail={"result": req.status, "amount": str(req.amount)})
    db.session.commit()
    return jsonify({"status": req.status, "note": req.note})


# ---------------------------------------------------------------- redeems (winnings -> wallet): reconcile unclear outcomes
@site_bp.route(f'{A}/redeems')
@admin_required()
def admin_redeems():
    from app.models_site import RedeemRequest
    from app.services import wallet as ledger
    q = RedeemRequest.query
    if request.args.get('status'):
        q = q.filter(RedeemRequest.status.in_(request.args['status'].split(',')))
    rows = q.order_by(RedeemRequest.id.desc()).limit(200).all()
    names = {p.id: p.username for p in Player.query.filter(Player.id.in_({r.player_id for r in rows} or [0]))}
    return jsonify({"items": [{
        "id": r.id, "player": names.get(r.player_id), "game": r.account.game.name, "game_login": r.account.provider_username,
        "deposit": ledger.fmt(r.deposit_cents), "balance": ledger.fmt(r.balance_cents), "payout": ledger.fmt(r.payout_cents),
        "voided": ledger.fmt(r.void_cents), "status": r.status, "note": r.note, "created_at": iso(r.created_at)} for r in rows]})


@site_bp.route(f'{A}/redeems/<int:rid>', methods=['PATCH'])
@admin_required()
def admin_redeem_update(rid):
    """needs_review / stuck 'processing': after checking the provider panel, either confirm the winnings really left the game
    (credits the wallet payout, once) or confirm they did not (releases the deposit so the player can retry)."""
    from app.models_site import RedeemRequest
    from app.services import wallet as ledger
    action = _body().get('action')
    if action not in ('resolve_completed', 'resolve_failed') or not db.session.get(RedeemRequest, rid):
        return json_error("Invalid request")
    outcome = 'completed' if action == 'resolve_completed' else 'failed'
    claimed = 0
    for from_status in ('needs_review', 'processing'):
        claimed = (RedeemRequest.query.filter_by(id=rid, status=from_status).update({"status": outcome}, synchronize_session=False))
        if claimed:
            break
    db.session.commit()
    if claimed != 1:
        return json_error("Only redeems needing review can be resolved.", 409)
    rr = db.session.get(RedeemRequest, rid)
    rr.processed_at = utcnow()
    if outcome == 'completed':
        ledger.credit(rr.player_id, rr.payout_cents, 'redeem', 'redeem_request', rr.id)  # idempotent
        rr.note = "Reconciled by staff: winnings left the game."
        _notify(rr.player_id, "Winnings redeemed", f"${ledger.fmt(rr.payout_cents)} was added to your wallet from {rr.account.game.name}.")
    else:
        rr.deposit_lock_id, rr.note = None, "Reconciled by staff: nothing left the game; you can try again."
        _notify(rr.player_id, "Redeem not completed", "Nothing was taken from your game. You can try again.")
    audit("redeem.resolve", target=str(rid), detail={"result": outcome})
    db.session.commit()
    return jsonify({"status": outcome})
