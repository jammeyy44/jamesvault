# JamesVault — Phase 1 Repository Audit (GameAPI)

Audited: `GameAPI/` @ clone of github.com/petergt44/GameAPI, plus the fixes made while getting it to run.
Environment: Python 3.10 venv, SQLite (`DATABASE_URL=sqlite:///gameapi.db`), no Redis, no PostgreSQL.

## 1. What the repo actually is

A Flask + Flask-RESTX service of **web-scraping/automation adapters for third-party "agent panel" back offices**
(5 provider categories, 17 providers). Each adapter logs into a provider's agent web panel with a shared
store/agent credential, and performs: add_user, recharge, redeem, change_password, get_balances, get_agent_balance.
It is **not** a game platform: there is no game catalog, no game metadata, no launch URL, no player concept.

| Category | Providers | Mechanism |
|---|---|---|
| 1 | Gameroom, Cash Machine, Mr All In One, Cash Frenzy, Mafia, King of Pop | HTTP form/JSON to agent server, token cached |
| 2 | Game Vault, Vegas Sweeps, Juwa | agent web panel requests |
| 3 | Orion Stars, Panda Master, Milkyway, Fire Kirin | HTML scraping (BeautifulSoup) + **2Captcha CAPTCHA solving** |
| 4 | River Sweeps | AES-encrypted payloads (pycryptodome) |
| 5 | Vblink, Egame, Ultra Panda | subclass of Cat. 4 + CAPTCHA |

## 2. Confirmation of preliminary findings

| Finding | Verdict |
|---|---|
| Endpoints are login/add_user/recharge/redeem/reset_password/balance/agent_balance only | **Confirmed.** `/category1..5/*` plus `/vblink/login`. No catalog or launch endpoint. |
| Recharge/redeem move credit between agent and a provider player account, not a platform wallet | **Confirmed.** They take `provider_id`, `username`, `amount` and operate on the provider panel. No platform ledger exists. |
| Auth is admin-only; no player auth | **Confirmed and worse:** the `/categoryX/*` endpoints have **no authentication at all** (no `token_required`/login on any of them). The `Token` model exists but is never checked. |
| CAPTCHA key implies panel automation / ToS risk | **Confirmed.** Cat. 3 and 5 solve CAPTCHAs via 2Captcha to log in to agent panels. This circumvents access controls and is very likely against the providers' terms. |

## 3. Defects found (existing code)

Fixed while setting up: missing `wraps` import (base_service), missing `BaseGameService` import (category5), `api`/admin blueprints not attached to the served app, `AnonymousUser.is_authenticated` was a method (always truthy), `user_loader` returned None, login redirected to nonexistent endpoint, `requirements.txt` missing flask-admin / redis / beautifulsoup4 / 2captcha-python and containing the Linux-only `pkg_resources==0.0.0`.

**Still open:**
- `BaseGameService._make_request` references undefined `full_url`, and `retry_on_failure` uses `time` without importing it → any code path using them raises NameError.
- `app/services/factory.py` and `app/routes/api/game.py` / `game_service.py` are dead, stale code (wrong constructors, provider names that don't match seeds, no Category5).
- `/admin/api/{accounts,tokens,logs}` documented in README are **not registered**; `app/routes/admin/__init__.py` references an undefined `app` and imports `flask_admin` for nothing.
- Admin model `Admin` (dashboard login) and `Account` (API accounts, with `type` incl. PLAYER) are separate and unrelated; `Account.password` is a plain `String(200)` with no hashing helper.
- `Admin.password_hash` is `String(128)`; werkzeug's default scrypt hashes exceed that on PostgreSQL.
- Request bodies, **including provider passwords**, are logged at INFO (`current_app.logger.info(f"Received request data: {data}")`, and `provider.to_dict()`).
- Provider endpoints accept the provider's own `username`/`password` from the caller.
- Money amounts are `Float`; no idempotency keys, no transaction table, no reconciliation.
- Dashboard `Provider.password` stored in plaintext.
- Security headers set `Strict-Transport-Security` unconditionally and CSP `default-src 'self'` (breaks Swagger UI/external images); CORS only for `/api/*`, which doesn't exist.
- `seed_providers.py` commits real-looking shared agent credentials (since removed) to git; they must be treated as compromised and rotated. `seed_admins.py` creates `admin/admin123`.
- Migrations: two Alembic revisions; not verified against current models. `db.create_all()` was used locally.
- Tests: `tests/test_auth.py` fails (404, endpoint `/admin/api/login` doesn't exist); `test_game_services.py` and `test_logging.py` are empty. **Baseline: 1 test, 1 failing.**
- Flask 2.0.3 / Werkzeug 2.0.3 / Jinja 3.0.3 / requests 2.27.1 / urllib3 1.26 are old and carry known CVEs.

## 4. Feature feasibility matrix

| Requested feature | Status |
|---|---|
| Frontend design system, home, nav, responsive shell | Needs frontend only — **buildable now** |
| Player registration/login/reset/profile | **Needs backend** (new player auth, email delivery config) |
| Game lobby with verified catalog | **Blocked on data:** no catalog exists. Needs an admin-managed catalog (own metadata/artwork) or a provider catalog source. |
| Game launch | **Not supported by any existing endpoint.** Cannot be built without provider-supplied launch contracts. Will be documented, not simulated. |
| Wallet / deposits / withdrawals | **Blocked:** no payment processor, no platform ledger; recharge/redeem ≠ deposit. Needs a ledger + licensed payment provider. |
| Promotions, rewards, wheel, referrals | Buildable (new models), but any reward that credits provider balance depends on recharge adapters whose reliability is questionable. |
| Tournaments / leaderboards | Management framework only; no provider event feed exists. |
| Verified winners feed | Not possible; no verified win events. Ship empty/disabled. |
| Support tickets | Buildable. |
| Admin enhancements | Buildable on existing Flask admin (after fixing its structure). |

## 5. Risks that need an owner's decision

1. **Legal/licensing.** The repo's business is operating sweepstakes/casino-style agent accounts. Real-money or sweepstakes play requires jurisdictional licensing and provider agreements. The brief already says to gate deposits/withdrawals on this; I will keep everything money-related behind a disabled feature flag.
2. **Provider access.** CAPTCHA-solving login to agent panels is fragile and likely contrary to provider terms. Production should use official provider APIs/contracts.
3. **Credentials.** Treat all values in `seed_providers.py` as leaked; move to env/secret store.
4. **Exposed endpoints.** Until auth is added, anyone reaching the API can move credit on provider accounts. Do not expose this service publicly as-is.

## 6. Proposed build order (what can honestly be delivered)

1. Backend hardening: auth on provider routes, stop logging secrets, fix undefined names, idempotency + ledger tables, test baseline.
2. Player auth API (+ password reset via configured email), favorites, notifications, tickets, promotions/claims, referrals, tournaments (framework), audit log. Alembic migrations.
3. Next.js + TS + Tailwind + shadcn frontend: design system, home, lobby (driven by an admin-managed catalog), auth, dashboard, promotions, referrals, tournaments, support. No VIP, no FAQ.
4. Admin enhancements, tests, deployment docs.
5. Game launch and payments: documented as **not implemented** pending provider contracts and licensing.
