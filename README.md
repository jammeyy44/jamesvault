# JamesVault

Premium gaming site: a **Next.js** frontend (`web/`) on top of the Flask **GameAPI** (`GameAPI/`).
Read [AUDIT.md](AUDIT.md) first: it explains what the underlying provider API can and cannot do.

## Status: what is real and what is not

| Area | Status |
|---|---|
| Design system, responsive shell, home, lobby, Bonus Zone, referrals, support, legal pages | Implemented |
| Player registration / login / logout / forgot + reset password / change password / email change | Implemented (hashed passwords, CSRF, rate limits, single-use 30-min reset tokens) |
| Game lobby | Implemented, driven by an admin-managed catalog. `seed_site.py` lists the 17 real providers as catalog entries (no artwork) |
| Favorites, notifications, support tickets with staff replies | Implemented |
| Special offers (promotions), claims, reward wheel, referrals | Implemented; promotion claims and wheel prizes are **recorded and fulfilled by staff**, uniqueness constraints block double claims, wheel outcome is chosen server-side |
| Admin panel (`/admin`) | Implemented inside the same site, same login as players. Accounts with a staff role (`superadmin` / `content` / `support`) get an "Admin panel" menu entry: content CRUD, queues, tickets, API tokens, role management, audit log |
| **Bonus Zone** (replaces Promotions) | Implemented. Diamonds are earned by tasks the server can verify (confirm email via a real link, daily login, 7-day streak, deposits from the wallet ledger, confirmed referrals) and spent in the **Lucky Shop**: five boxes, each holding one fixed, disclosed reward. **Rewards apply instantly, with no agent**: $2/$3/$4 free play and the $5 bonus go straight into the player's **bonus balance**; the 20% box starts a timed **Deposit Boost**. Premium opening ceremony (shake, light burst, particles, reward reveal; honours reduced motion). Live promotions still show as "Special offers"; `/promotions` and the removed tournaments redirect here |
| Home page | Wide banner slider (Bonus Zone / Games, autoplay with segmented progress, swipe, keyboard, pause on hover), then a "Refer your friends" strip, then the game lobby |
| **Bonus balance + Deposit Boost** | Two balances per player: the **wallet** (real money, withdrawable) and the **bonus balance** (free play / bonus credit, spendable on games only, never withdrawable). While a Deposit Boost is active (countdown banner in the wallet, deposit popup and Bonus Zone) every deposit earns the boost percentage into the bonus balance: deposit $20 with +20% -> $20 wallet + $4 bonus. The percentage is the boost running when the deposit *order was created*; it is credited once, only when the payment is confirmed, and a refund takes back its proportional share of the bonus. **Add Cash** on a game can spend either balance; when the wallet is under $1 one tap adds the whole bonus balance to the game (bonus minimum $1, or everything when less). All movements are atomic, idempotent ledger entries |
| **Free-spin wheel** (Bonus Zone + dashboard Rewards tab) | Replaces the old staff-fulfilled daily wheel. Unlocked by a **confirmed wallet deposit in the last 24 hours** (refunded deposits do not count); **one spin per 24 hours** (enforced in the database per deposit). A live countdown shows the time left to spin, or until the next spin. The prize is picked on the server from a CSPRNG using admin-editable weights, the odds are shown on the page, and it is **applied instantly**: diamonds -> diamond balance, free play -> bonus balance, boost -> Deposit Boost. Defaults: 1/2/4 diamonds, $2/$3/$5 free play, 5% boost. Needs `JV_ENABLE_WALLET` (deposits) |
| **Cashout rules / Redeem winnings** | Players take winnings out of a game with **Redeem** (game panel -> Redeem). The limits come from the player's **most recent confirmed deposit** (refunded deposits are ignored): $5 -> $50/$50; $5-$9 -> $50/$100; $10-$16 -> $50/x12; $17-$25 -> x3/x12; $26-$30 -> x3/x12; $30+ -> x3/x12 capped at $500 (x3 = 3 times the deposit). Deposits start at **$5**. Anything above the maximum is **voided**: the player sees the exact payout/voided amounts and must tick a confirmation first. Order of operations: balance read from the provider, deposit locked (one redeem per deposit), whole balance taken out of the game, **then** the payout credited to the wallet; a refused call changes nothing, an unclear one is held for staff (Admin -> redeems). Band edges are in `app/services/cashout_rules.py` (documented, unit-tested). Needs the providers' redeem call, which is unverified against real panels |
| Deposit popup | Choosing a payment method opens an amount popup (editable amount, +5/+10/+25/X2, reset). Methods the provider only accepts fixed amounts for (CashApp, Apple/Google Pay, Card, Chime) snap to the next accepted amount; others use `DEPOSIT_MIN`/`DEPOSIT_MAX`, enforced server-side |
| Game access ("Get access" / login details / Add Cash) | Implemented. `Play` opens a panel: create the player's game login (idempotent), view username/password (encrypted at rest, reveal + copy), add cash with +5/+10/+25/x2. Needs `JV_ENABLE_GAME_ACCOUNTS=true` (live adapters, **unverified against real panels**) or `JV_SANDBOX=true` (labelled test data, refused in production) |
| **Wallet + payments (Paydora)** | Implemented behind `JV_ENABLE_WALLET`. Header wallet icon opens the Wallet panel (balance, Deposit / Cashout / History). Integer-cents ledger with idempotent, atomic credits/debits. Deposits: provider order -> pay page -> **signed webhook** (verified, deduplicated, re-confirmed with the provider) -> credit. Cashouts: funds held at request, superadmin approves, sent once, auto-refund on cancel. Add Cash from a game spends wallet funds and recharges automatically. **Untested against the live provider**: no key was available, tests use a fake |
| Game launch (open the game itself) | Not implemented. No provider launch contract exists; `POST /games/<slug>/launch` returns 501 |
| Email verification | Not implemented (reset emails require SMTP) |
| Verified-winners feed | Not implemented (no verified win events exist); omitted rather than faked |
| Component unit tests (vitest) | Not written. Backend and Playwright e2e tests exist |
| Provider adapters (`/category1..5`) | Preserved, now require an admin session or API token. They scrape agent panels (some via CAPTCHA solving), which is fragile and likely against provider terms |

Money-related features stay behind feature flags (`JV_ENABLE_WALLET`, `JV_ENABLE_GAME_ACCOUNTS`) until licensing, jurisdiction and provider contracts are verified.

### Payments setup (Paydora)
1. Set `PAYDORA_API_KEY` (a `pk_...` key) and `PAYDORA_WEBHOOK_SECRET` (the `whsec_...` shown once when you add the endpoint) in the backend environment, never in code. `JV_ENABLE_WALLET=true`.
2. In the provider dashboard add the webhook URL `https://<your-domain>/api/v1/webhooks/paydora` (all events).
3. Behind a reverse proxy set `TRUSTED_PROXY_COUNT` (number of proxies appending to `X-Forwarded-For`): deposits must send the customer's real public IP.
4. Method tiles come from the provider; use Admin -> Payment methods only for labels/badges/order. Badges are text you enter ("No fee", "+15%"), so only publish claims that are true. Wallet withdrawals: **minimum $50** (a wallet holding exactly $50 can withdraw it all) and maximum $500 per withdrawal (`CASHOUT_MIN` / `CASHOUT_MAX`); the Cashout tab states the minimum, shows how much is still needed, and blocks under-minimum requests (the server enforces it too); card payouts are not supported (we never handle card numbers).
5. Direct-pay Chime (`isChimney`) payments are never auto-credited (memo text is untrusted): they land in Admin -> Unmatched payments for a staff member to verify and credit once.
6. Ambiguous outcomes (timeouts) put a cashout or game credit in `needs_review` with funds held, never retried blindly; resolve by hand after checking the provider.

## Run locally

Requirements: Python 3.10 (pinned deps do not support 3.12+), Node 20+.

```bash
# Backend (SQLite for development; Redis optional: caching is skipped if absent)
cd GameAPI
py -3.10 -m venv venv && venv\Scripts\activate        # source venv/bin/activate on Linux/macOS
pip install -r requirements-dev.txt
set DATABASE_URL=sqlite:///gameapi.db                  # export on Linux/macOS; use PostgreSQL in production
python seed_providers.py                               # NOTE: seeds credentials committed in the repo, rotate them
python seed_site.py --dev-sample                       # tables, admin, catalog; sample content only with the flag
python run.py                                          # http://localhost:8080

# Frontend
cd ../web
cp .env.example .env.local
npm install
npm run dev                                            # http://localhost:3000
```

**Admin access.** There is one login (`/login`). Staff access is a role on the player account (`player` | `support` | `content` | `superadmin`).
`python seed_site.py` pre-creates a superadmin account for each email in `ADMIN_EMAILS` (default `jammeyy44@gmail.com`) with an unusable
random password; the owner sets their own via **Forgot password** on `/login` (in development without SMTP the reset link is written to the
Flask log). Registration never grants a role, so those addresses cannot be claimed by signing up. A superadmin can change other accounts'
roles in Admin panel -> Players (not their own). The old Flask HTML admin (`/admin/login`) has been removed.

## Configuration

All backend settings are env vars (see `GameAPI/.env.example`): brand, feature flags, SMTP, cookie security, CORS.
Frontend brand/palette: `web/lib/brand.ts` and `web/tailwind.config.ts`. The browser only talks to the Next.js origin;
`/api/v1/*` is proxied to Flask (`BACKEND_URL`), so cookies are first-party and no CORS is needed.

## Database and migrations

**Upgrading an existing database:** `python seed_site.py` is safe to run on every deploy. It creates missing tables and *adds any new columns* to existing tables (additive only, via `app/utils/schema.py`; nothing is dropped or rewritten), seeds default Bonus Zone tasks/boxes without overwriting edits, and removes retired tasks.

Dev uses `db.create_all()` (done by `seed_site.py`). For PostgreSQL create a migration for the new tables and review it
before applying:

```bash
flask db migrate -m "jamesvault site tables" && flask db upgrade
```

The two pre-existing Alembic revisions were not verified against current models; review the autogenerated diff.
Schema changes: new `players.role` column; the legacy `admin` table is no longer used by the site.

## Tests

```bash
cd GameAPI && pytest tests              # 257 tests: auth, CSRF, reset tokens, claims idempotency, wheel, referrals,
                                        # support privacy, admin authorization, provider-route auth
cd web && npx next build && npm start   # with Flask running and seeded `--dev-sample`:
# e2e needs the API started with JV_SANDBOX=true JV_ENABLE_WALLET=true JV_RATE_LIMITS=false (never allowed in production)
npx playwright install chromium && npm run test:e2e   # 26 checks x desktop + mobile (no VIP/FAQ, no overflow, slider, wallet + deposit popup + boost, game access, bonus-to-game, redeem under the cashout table, Bonus Zone + box opening, free-spin wheel)
```

Baseline before changes was 1 test, failing. All current tests pass.

## Production

- Set `JV_ENV=production`, a strong `SECRET_KEY`, `JV_COOKIE_SECURE=true`, `DATABASE_URL` (PostgreSQL, least-privilege user), `ADMIN_EMAILS`, SMTP settings (needed for the admin's first password reset), `FRONTEND_URL`.
- Run Flask with `gunicorn -w 4 -b 127.0.0.1:8080 "run:app"` and Next with `npm run build && npm start`, behind a TLS-terminating reverse proxy (nginx/Caddy) that forwards `X-Forwarded-Proto` and `X-Forwarded-For`, serves HTTPS only, and does not expose port 8080.
- Rate limiting is per process: with multiple workers add proxy-level limits (e.g. nginx `limit_req` on `/api/v1/auth/`).
- Health check: `GET /api/v1/health` (200 ok / 503 database unavailable).
- Logs: request lines go to stdout (collect with your platform); passwords and request bodies are no longer logged. Audit records live in `audit_logs` and are visible to superadmins.
- Backups: nightly `pg_dump` of the database, retained and restore-tested; the audit and claim tables are the records of reward obligations.
- **Before launch:** rotate the provider credentials in `seed_providers.py`, remove them from git history, supply real legal text (`web/lib/legal.ts`), and complete licensing/jurisdiction review.

## Troubleshooting

- `{"error":"Resource not found"}` at `http://localhost:8080/`: that is the API; use the web app on `:3000` or `/swagger/`.
- `403 Missing or invalid CSRF token`: the client must send `X-CSRF-Token` from `GET /api/v1/csrf` (the web app does this automatically and refreshes it after login/logout).
- Redis connection refused at startup: expected without Redis; provider session caching is simply skipped.
- Password reset emails not arriving: configure `SMTP_*`; in development the link is printed in the Flask log.


## Notes

- **Tournaments were removed** from the product (navigation, pages, home slide, admin tab and the Bonus Zone task). Old `/tournaments` links redirect to the Bonus Zone. The database tables and API endpoints from the earlier build are still present but unused and unreachable from the UI; they can be dropped in a later clean-up migration.
- Bonus balance and Deposit Boost are only as safe as the rules around them: free play and bonuses are instant credits, so decide your wagering / cashout policy for winnings made with bonus funds before launch (the provider side of that is not controlled from this app).

- **Open policy question: deposits in the wallet are still withdrawable.** The cashout table limits what can be *redeemed from a game*, but money deposited into the wallet can still be cashed out directly from the Cashout tab without being played. If deposits should only be spendable on games (only redeemed winnings withdrawable), the wallet needs a separate "winnings" balance; this is not built yet.


## Game panel (Get access / account / Cash Out)
- Players see the game art, name and category, an optional download button (the game's `download_url`), a live balance with "Last update", **Add Cash**, **Cash Out**, username/password with copy, **Reset password** and a trash button to **remove the login** (refused while the game holds money or a request is pending).
- Admin -> Game catalog: upload a **thumbnail** (PNG/JPEG/WebP, max 2 MB; type is checked from the file bytes, SVG refused). Files are stored in `UPLOAD_DIR` (default `GameAPI/uploads`); use a persistent volume in production.
- Real provider logins for Category 2/3 panels (Game Vault, Vegas Sweeps, Juwa, Orion Stars...) solve a CAPTCHA through 2Captcha: set `CAPTCHA_API_KEY` in `GameAPI/.env`. Without it the admin connection test shows "CAPTCHA_API_KEY is not set". The adapters are not verified against live panels.

## Coupons
Admin -> Coupons (superadmin): create a code worth bonus cash for **one person** (assigned by username/email) or **many people** (each account once, optional total cap, optional expiry). Players enter it under "Have a coupon?" on the home page; it is credited to the bonus balance instantly. Once-per-account is enforced by a database unique constraint; wrong, foreign and unknown codes get the same answer so codes cannot be probed. Run `python seed_site.py` once to create the new tables.
