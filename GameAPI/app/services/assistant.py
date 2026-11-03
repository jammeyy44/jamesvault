"""The voice assistant's brain: tools the AI may call, and the loop that runs them.

The AI never moves money. Read-only tools return facts. "propose_*" tools only VALIDATE a request against the real rules and hand
a proposal back; the website shows a Confirm card and the player's tap sends the real request through the normal endpoints
(with CSRF, rate limits, idempotency and every existing rule). Paying at the payment provider is always done by the player.
"""
import json
import logging
from decimal import Decimal, InvalidOperation

from flask import current_app

from app.models_site import CatalogGame, GameAccount
from app.services import assistant_llm, wallet as ledger
from app.services.gateway import get_gateway
from app.services.payments import PaymentError, get_payments, payments_mode

logger = logging.getLogger("jamesvault.assistant")

MAX_HISTORY = 8
MAX_TEXT = 300
MAX_ROUNDS = 4

TOOLS = [
    {"name": "get_game_balance", "description": "Read the live balance of the player's login on one game.",
     "parameters": {"type": "object", "properties": {"game": {"type": "string", "description": "Game name or slug, e.g. Game Vault"}}, "required": ["game"]}},
    {"name": "get_cashout_info", "description": "Exact cashout facts for the player's login on a game: the latest cash added to it, the minimum and maximum they can cash out, the current game balance, and whether cashing out is possible now.",
     "parameters": {"type": "object", "properties": {"game": {"type": "string"}}, "required": ["game"]}},
    {"name": "cashout_range_for", "description": "Calculate the cashout range (minimum and maximum) for a hypothetical amount of cash added to a game, from the official table. Use for 'if I deposit 20, what can I cash out?'.",
     "parameters": {"type": "object", "properties": {"cash_added": {"type": "number", "description": "Dollars added to the game"},
                                                      "source": {"type": "string", "enum": ["cash", "bonus"], "description": "cash = their own wallet money (default); bonus = bonus balance only"}}, "required": ["cash_added"]}},
    {"name": "list_deposit_methods", "description": "List the payment methods and the amounts each accepts for a deposit.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "propose_deposit", "description": "Prepare a deposit for the player to confirm. Only call it when you know the amount AND the method.",
     "parameters": {"type": "object", "properties": {"amount": {"type": "number", "description": "Dollars the player wants in their wallet"},
                                                      "method": {"type": "string", "description": "Payment method name, e.g. card, cashapp, chime"}},
                    "required": ["amount", "method"]}},
    {"name": "propose_add_cash", "description": "Prepare loading money into a game for the player to confirm.",
     "parameters": {"type": "object", "properties": {"game": {"type": "string"}, "amount": {"type": "number", "description": "Dollars to load"},
                                                      "source": {"type": "string", "enum": ["wallet", "bonus"], "description": "Where the money comes from; default wallet"}},
                    "required": ["game", "amount"]}},
    {"name": "propose_create_login", "description": "Prepare creating the player's login (username and password) on a game, for the player to confirm. Use when they ask for credentials, a login, access, or to start playing a game they have no login on.",
     "parameters": {"type": "object", "properties": {"game": {"type": "string"}}, "required": ["game"]}},
    {"name": "propose_reset_password", "description": "Prepare a new password for the player's existing game login, for the player to confirm. Use when they forgot or want to change their game password.",
     "parameters": {"type": "object", "properties": {"game": {"type": "string"}}, "required": ["game"]}},
    {"name": "get_login_name", "description": "The player's game login username (never the password). The password is shown only on the game page.",
     "parameters": {"type": "object", "properties": {"game": {"type": "string"}}, "required": ["game"]}},
    {"name": "propose_redeem_coupon", "description": "Prepare redeeming a coupon code, for the player to confirm. Spell the code back to the player.",
     "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "open_live_chat", "description": "Open the live operator chat window so the player can talk to a human operator.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "propose_chat_message", "description": "Prepare sending a text message to the live operator on the player's behalf, for the player to confirm. Read the message back first.",
     "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "The message to send, in the player's own words"}}, "required": ["text"]}},
    {"name": "propose_verify_email", "description": "Prepare sending the player a confirmation email so they can verify their address (needed for the 50% first-add bonus).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "get_recent_activity", "description": "The player's latest deposits, cash added to games, game cashouts and withdrawals with their status. Use for 'did my deposit arrive', 'what did I do lately'.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "navigate", "description": "Open a part of the website for the player.",
     "parameters": {"type": "object", "properties": {
         "target": {"type": "string", "enum": ["home", "games", "wallet", "wallet_withdraw", "bonus_zone", "refer", "support", "dashboard", "cashout_rules", "game"]},
         "game": {"type": "string", "description": "Game name, when target is game"},
         "screen": {"type": "string", "enum": ["play", "add_cash", "cash_out"], "description": "Which screen of the game; default play"}},
                    "required": ["target"]}},
]

PAGES = {"home": "/", "games": "/games", "bonus_zone": "/bonus-zone", "refer": "/refer", "support": "/support",
         "dashboard": "/dashboard", "cashout_rules": "/cashout-rules"}


def _money(v):
    return f"${Decimal(v):,.2f}"


def _amount(raw):
    try:
        a = Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return a if a.is_finite() and a > 0 else None


def _find_game(name):
    name = str(name or "").strip().lower()
    if not name:
        return None, "Which game?"
    games = CatalogGame.query.filter(CatalogGame.status != "hidden").all()
    exact = [g for g in games if g.slug.lower() == name or g.name.lower() == name]
    hits = exact or [g for g in games if name in g.name.lower() or name.replace(" ", "-") in g.slug.lower()]
    if not hits:  # how speech-to-text tends to write the names (accents differ: "fault", "inchua", "jio")
        said = "".join(ch for ch in name if ch.isalnum())
        sounds = {"juwa": ("jua", "jio", "chua", "jwa", "jewa", "dua", "joywa", "juah", "juaa", "juwah", "joa", "huwa"),
                  "gamevault": ("gamefault", "gameball", "gamebolt", "gamevolt", "gamewall", "gamevote", "gamevalt", "gameworld", "gamevaults", "fault", "vault")}
        two = any(w in name for w in ("2", "two", "too", "to ")) or said.endswith(("2", "two", "20"))
        for g in games:
            key = "".join(ch for ch in g.name.lower() if ch.isalnum())
            base = key[:-1] if key.endswith("2") else key
            for canon, alts in sounds.items():
                if base == canon and any(a in said for a in alts) and (key.endswith("2") == two):
                    hits.append(g)
                    break
    if not hits:  # speech-to-text often mishears names ("game volt", "jewa two"): fall back to the closest sounding name
        import difflib
        squash = lambda t: "".join(ch for ch in t.lower() if ch.isalnum())
        by_name = {squash(g.name): g for g in games}
        close = difflib.get_close_matches(squash(name), list(by_name), n=2, cutoff=0.62)
        hits = [by_name[c] for c in close[:1]]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, "I couldn't find that game. Available games: " + ", ".join(g.name for g in games[:8])
    return None, "That could be " + " or ".join(g.name for g in hits[:4]) + ". Which one?"


def _account(player, game):
    return GameAccount.query.filter_by(player_id=player.id, game_id=game.id, status="active").first()


# ------------------------------------------------------------------ tools
def t_get_game_balance(player, game):
    g, err = _find_game(game)
    if err:
        return {"error": err}
    acct = _account(player, g)
    if not acct:
        return {"error": f"The player has no login on {g.name} yet. They can get one on the game page."}
    gw = get_gateway()
    if gw is None:
        return {"error": "Game balances are not available right now."}
    try:
        return {"game": g.name, "balance": _money(gw.get_balance(acct))}
    except Exception:
        return {"error": f"Could not read the {g.name} balance right now."}


def t_get_cashout_info(player, game):
    from app.routes.site.redeem import _preview
    g, err = _find_game(game)
    if err:
        return {"error": err}
    acct = _account(player, g)
    if not acct:
        return {"error": f"The player has no login on {g.name} yet."}
    pv = _preview(player, g, acct)
    added = pv.get("added") or {}
    out = {"game": g.name, "cash_added_since_last_cashout": _money(added.get("cash", 0)), "bonus_added_since_last_cashout": _money(added.get("bonus", 0)),
           "latest_cash_added_that_sets_the_range": _money(pv["latest_deposit"]) if pv.get("latest_deposit") else None,
           "game_balance": _money(pv["game_balance"]) if pv.get("game_balance") is not None else None, "can_cash_out_now": bool(pv.get("can_redeem")),
           "reason_if_not": pv.get("reason")}
    if pv.get("rule"):
        out["cashout_minimum"], out["cashout_maximum"] = _money(pv["rule"]["min"]), _money(pv["rule"]["max"])
    if pv.get("mode") == "bonus":
        out["note"] = "This game was funded only by bonus: the balance must reach $60, then the wallet gets $10 for $60 to $90 or $20 for $91 and above."
    if pv.get("payout") is not None:
        out["would_receive_in_wallet"] = _money(pv["payout"])
        if pv.get("voided") and Decimal(pv["voided"]) > 0:
            out["amount_above_the_maximum_that_would_be_voided"] = _money(pv["voided"])
    return out


def t_cashout_range_for(player, cash_added, source="cash"):
    from app.services import cashout_rules as rules
    a = _amount(cash_added)
    if a is None:
        return {"error": "I need a dollar amount."}
    if source == "bonus":   # a game funded only by bonus follows the bonus rule, not the cash table
        return {"rule": "bonus-only game", "explanation": "Bonus can only be loaded into a game, never withdrawn directly. If a game is funded ONLY by bonus, its balance must reach $60 to cash out. "
                "Then the wallet is credited a fixed amount: $10 when the balance is $60 to $90, $20 when it is $91 or more. The rest of the balance is not carried over. "
                "If the player adds their own cash to that game too, the normal cash table applies instead."}
    rule = rules.limits(ledger.to_cents(a))
    if rule is None:
        return {"error": "Cash added under $5 does not unlock cashing out."}
    return {"cash_added": _money(a), "cashout_minimum": _money(Decimal(rule["min_cents"]) / 100), "cashout_maximum": _money(Decimal(rule["max_cents"]) / 100),
            "note": "Anything won above the maximum is voided by the system. Bonus added to the game does not count towards the range."}


def _deposit_methods():
    from app.routes.site.wallet import _decorate, _provider_methods
    if payments_mode() == "disabled":
        raise PaymentError("Deposits are not available yet.")
    return _decorate(_provider_methods(get_payments())["deposits"])


def t_list_deposit_methods(player):
    try:
        return {"methods": [{"name": m["name"], "accepted_amounts": m["amounts"] or "any amount in range"} for m in _deposit_methods()],
                "note": "The wallet receives the amount rounded to whole dollars (for example pay $24.99, get $25)."}
    except PaymentError as e:
        return {"error": str(e)}


def t_propose_deposit(player, amount, method):
    a = _amount(amount)
    if a is None:
        return {"error": "I need a valid dollar amount."}
    try:
        methods = _deposit_methods()
    except PaymentError as e:
        return {"error": str(e)}
    want = str(method or "").strip().lower()
    hit = [m for m in methods if want and (want == m["value"] or want in m["name"].lower() or m["name"].lower() in want)]
    if len(hit) != 1:
        return {"error": "Which payment method? Options: " + ", ".join(m["name"] for m in methods)}
    m = hit[0]
    if m["amounts"]:
        match = [x for x in m["amounts"] if Decimal(str(x)) == a] or [x for x in m["amounts"] if ledger.whole_dollars(ledger.to_cents(x)) == ledger.to_cents(a.quantize(Decimal("1")))]
        if not match:
            return {"error": f"{m['name']} accepts: " + ", ".join(_money(x) for x in m["amounts"]) + ". Which amount?"}
        pay = Decimal(str(match[0])).quantize(Decimal("0.01"))
    else:
        cfg = current_app.config
        if not (cfg["DEPOSIT_MIN"] <= a <= cfg["DEPOSIT_MAX"]):
            return {"error": f"Deposits are between {_money(cfg['DEPOSIT_MIN'])} and {_money(cfg['DEPOSIT_MAX'])}."}
        pay = a
    credit = Decimal(ledger.whole_dollars(ledger.to_cents(pay))) / 100
    proposal = {"type": "deposit", "method_id": m["id"], "method_name": m["name"], "pay": f"{pay:.2f}", "credit": f"{credit:.2f}",
                "summary": f"Deposit with {m['name']}: you pay {_money(pay)} and {_money(credit)} is added to your wallet."}
    return {"proposal": proposal, "tell_the_player": "The confirmation card is on screen. Ask them to confirm; they will then be sent to the payment page."}


def t_propose_add_cash(player, game, amount, source="wallet"):
    from app.routes.site.accounts import _bonus_for, cash_bonus_info
    g, err = _find_game(game)
    if err:
        return {"error": err}
    acct = _account(player, g)
    if not acct:
        return {"error": f"There is no login on {g.name} yet. Open the game page to get one first.", "navigate": f"/game/{g.slug}"}
    a = _amount(amount)
    cfg = current_app.config
    if a is None:
        return {"error": "I need a valid dollar amount."}
    if not (cfg["CASH_MIN"] <= a <= cfg["CASH_MAX"]) and source != "bonus":
        return {"error": f"Adding cash is between {_money(cfg['CASH_MIN'])} and {_money(cfg['CASH_MAX'])}."}
    cents = ledger.to_cents(a)
    source = "bonus" if source == "bonus" else "wallet"
    if source == "wallet" and player.wallet_cents < cents:
        return {"error": f"The wallet has {_money(Decimal(player.wallet_cents) / 100)}, which is not enough. A deposit comes first."}
    if source == "bonus":
        if player.bonus_cents < cents:
            return {"error": f"The bonus balance is {_money(Decimal(player.bonus_cents) / 100)}."}
        if player.wallet_cents >= 100:
            return {"error": "Bonus balance can be used once the wallet is under $1. Use the wallet first."}
        if not (a >= 1 or cents == player.bonus_cents):
            return {"error": "Adding from bonus needs at least $1 (or the whole bonus balance)."}
    gw = get_gateway()
    if gw is not None:
        try:
            live = Decimal(gw.get_balance(acct))
            if live >= 1:
                return {"error": f"{g.name} still has {_money(live)}. Cash can be added again once the game is under $1."}
        except Exception:
            return {"error": f"I couldn't check the {g.name} balance, so I can't load it right now."}
    bonus, pct = Decimal("0"), 0
    if source == "wallet":
        info = cash_bonus_info(player)
        pct = info["percent"]
        bonus = _bonus_for(a, pct)
    total = a + bonus
    extra = f", plus a {_money(bonus)} {pct}% bonus" if bonus else ""
    proposal = {"type": "add_cash", "slug": g.slug, "game": g.name, "amount": f"{a:.2f}", "source": source, "bonus": f"{bonus:.2f}", "bonus_percent": pct,
                "total": f"{total:.2f}",
                "summary": f"Add {_money(a)} from your {'bonus balance' if source == 'bonus' else 'wallet'} to {g.name}{extra}. {_money(total)} will be in the game."}
    return {"proposal": proposal, "tell_the_player": "The confirmation card is on screen. Ask them to confirm."}


def _login_game(player, game):
    """(game, account, error) for the login tools."""
    from app.routes.site.accounts import _provider_off
    g, err = _find_game(game)
    if err:
        return None, None, err
    if g.status == "maintenance" or _provider_off(g):
        return g, None, f"{g.name} is under maintenance right now. Please try again later."
    if get_gateway() is None:
        return g, None, "Game logins are not available yet."
    return g, _account(player, g), None


def t_propose_create_login(player, game):
    g, acct, err = _login_game(player, game)
    if err:
        return {"error": err}
    if acct:
        return {"error": f"They already have a login on {g.name}: the username is {acct.provider_username}. They can see the password on the game page, or you can offer to reset it.",
                "action": {"type": "navigate", "path": f"/game/{g.slug}"}}
    proposal = {"type": "create_login", "slug": g.slug, "game": g.name,
                "summary": f"Create your {g.name} login (username and password). The password will be shown on the {g.name} page, never read aloud."}
    return {"proposal": proposal, "tell_the_player": "The confirmation card is on screen. Ask them to confirm."}


def t_propose_reset_password(player, game):
    g, acct, err = _login_game(player, game)
    if err:
        return {"error": err}
    if not acct:
        return {"error": f"They have no login on {g.name} yet. Offer to create one."}
    proposal = {"type": "reset_password", "slug": g.slug, "game": g.name,
                "summary": f"Reset the password of your {g.name} login ({acct.provider_username}). The old password stops working and the new one is shown on the {g.name} page, never read aloud."}
    return {"proposal": proposal, "tell_the_player": "The confirmation card is on screen. Ask them to confirm."}


def t_get_login_name(player, game):
    g, err = _find_game(game)
    if err:
        return {"error": err}
    acct = _account(player, g)
    if not acct:
        return {"error": f"They have no login on {g.name} yet."}
    return {"game": g.name, "username": acct.provider_username, "note": "The password is only shown on the game page; I cannot read it out."}


def t_propose_redeem_coupon(player, code):
    import re
    c = re.sub(r"[^A-Za-z0-9_-]", "", str(code or "")).upper()
    if not (3 <= len(c) <= 40):
        return {"error": "I didn't catch a valid coupon code. Please spell it out."}
    proposal = {"type": "redeem_coupon", "code": c, "summary": f"Redeem the coupon code {c}. Check the code is exactly right, then confirm."}
    return {"proposal": proposal, "tell_the_player": "The confirmation card is on screen. Read the code back and ask them to confirm."}


def t_propose_chat_message(player, text):
    t = " ".join(str(text or "").split())[:500]
    if len(t) < 2:
        return {"error": "What should the message say?"}
    return {"proposal": {"type": "chat_message", "text": t, "summary": f"Send this message to the live operator: \"{t}\""},
            "tell_the_player": "The confirmation card is on screen. Read the message back and ask them to confirm."}


def t_propose_verify_email(player):
    if player.email_verified:
        return {"error": "Their email is already verified."}
    proposal = {"type": "verify_email", "summary": f"Send a confirmation email to {player.email}. Open it and tap the link to verify."}
    return {"proposal": proposal, "tell_the_player": "The confirmation card is on screen. Ask them to confirm."}


def t_get_recent_activity(player):
    from app.models_site import CashRequest, PaymentOrder, RedeemRequest, WithdrawalOrder
    rows = []
    for o in PaymentOrder.query.filter_by(player_id=player.id).order_by(PaymentOrder.id.desc()).limit(4):
        rows.append((o.created_at, f"deposit {_money(Decimal(o.amount_cents) / 100)} by {o.method_name}: {o.status}"))
    for c in CashRequest.query.filter_by(player_id=player.id).order_by(CashRequest.id.desc()).limit(4):
        extra = f" plus {_money(c.bonus_amount)} bonus" if c.bonus_amount and Decimal(c.bonus_amount) > 0 else ""
        rows.append((c.created_at, f"added {_money(c.amount)}{extra} to {c.account.game.name} from the {c.source}: {c.status}"))
    for r in RedeemRequest.query.filter_by(player_id=player.id).order_by(RedeemRequest.id.desc()).limit(3):
        rows.append((r.created_at, f"cashed out {r.account.game.name} to the wallet, {_money(Decimal(r.payout_cents) / 100)} paid: {r.status}"))
    for w in WithdrawalOrder.query.filter_by(player_id=player.id).order_by(WithdrawalOrder.id.desc()).limit(3):
        rows.append((w.created_at, f"withdrawal {_money(Decimal(w.amount_cents) / 100)} via {w.method_name}: {w.status}"))
    rows.sort(key=lambda x: x[0], reverse=True)
    return {"latest_first": [f"{t:%b %d %H:%M} UTC: {text}" for t, text in rows[:8]] or ["no activity yet"]}


def t_navigate(player, target, game=None, screen="play"):
    if target == "wallet":
        return {"action": {"type": "open_wallet"}}
    if target == "wallet_withdraw":
        return {"action": {"type": "open_wallet", "tab": "cashout"}}
    if target in PAGES:
        return {"action": {"type": "navigate", "path": PAGES[target]}}
    if target == "game":
        g, err = _find_game(game)
        if err:
            return {"error": err}
        suffix = {"add_cash": "?add=1", "cash_out": "?cashout=1"}.get(screen, "")
        return {"action": {"type": "navigate", "path": f"/game/{g.slug}{suffix}"}}
    return {"error": "I can't open that."}


def run_tool(player, name, args):
    try:
        if name == "get_game_balance":
            return t_get_game_balance(player, args.get("game"))
        if name == "get_cashout_info":
            return t_get_cashout_info(player, args.get("game"))
        if name == "cashout_range_for":
            return t_cashout_range_for(player, args.get("cash_added"), args.get("source") or "cash")
        if name == "list_deposit_methods":
            return t_list_deposit_methods(player)
        if name == "propose_deposit":
            return t_propose_deposit(player, args.get("amount"), args.get("method"))
        if name == "propose_add_cash":
            return t_propose_add_cash(player, args.get("game"), args.get("amount"), args.get("source") or "wallet")
        if name == "propose_create_login":
            return t_propose_create_login(player, args.get("game"))
        if name == "propose_reset_password":
            return t_propose_reset_password(player, args.get("game"))
        if name == "get_login_name":
            return t_get_login_name(player, args.get("game"))
        if name == "propose_redeem_coupon":
            return t_propose_redeem_coupon(player, args.get("code"))
        if name == "open_live_chat":
            return {"action": {"type": "open_live_chat"}}
        if name == "propose_chat_message":
            return t_propose_chat_message(player, args.get("text"))
        if name == "propose_verify_email":
            return t_propose_verify_email(player)
        if name == "get_recent_activity":
            return t_get_recent_activity(player)
        if name == "navigate":
            return t_navigate(player, args.get("target"), args.get("game"), args.get("screen") or "play")
    except Exception:
        logger.exception("assistant tool %s failed", name)
        return {"error": "That didn't work. Please try again."}
    return {"error": "Unknown tool."}


# ------------------------------------------------------------------ prompt + loop
LIVE_WORDS = ("balance", "cash out", "cashout", "cash-out", "withdraw", "how much", "range", "limit", "redeem", "worth", "have in", "guess out", "gash out",
              "minimum", "maximum", "can i get", "can i take")


def _game_facts(player, acct, live):
    """One line of exact facts about a login. Database numbers always; the live game balance only when live=True (it is a provider call)."""
    from app.routes.site.redeem import _added_to_game
    from app.models_site import RedeemRequest
    from app.services import cashout_rules as rules
    name = acct.game.name
    added = _added_to_game(acct)
    cash, bonus = Decimal(added["cash"]), Decimal(added["bonus"])
    parts = [f"{name}: cash added since the last cashout {_money(cash)}, bonus added {_money(bonus)}"]
    bal_cents = None
    if live:
        gw = get_gateway()
        try:
            bal_cents = ledger.to_cents(gw.get_balance(acct)) if gw is not None else None
        except Exception:
            bal_cents = None
        parts.append(f"live game balance {_money(Decimal(bal_cents) / 100)}" if bal_cents is not None else "live game balance could not be read right now")
    if cash == 0 and bonus > 0:
        parts.append("funded only by bonus: cashing out needs a balance of $60; then the wallet gets $10 (balance $60 to $90) or $20 ($91 and above)")
    else:
        dep = rules.latest_game_deposit(player.id, acct.id)
        rule = rules.limits(dep.amount_cents) if dep else None
        if rule is None:
            parts.append("no cash of their own added yet, so cashing out is not unlocked (add $5 or more of their own cash)")
        else:
            lo, hi = rule["min_cents"], rule["max_cents"]
            parts.append(f"latest cash added that sets the range {_money(Decimal(dep.amount_cents) / 100)}; CASHOUT RANGE minimum {_money(Decimal(lo) / 100)}, maximum {_money(Decimal(hi) / 100)}")
            done = RedeemRequest.query.filter_by(deposit_lock_id=dep.id).first() is not None
            if done:
                parts.append("already cashed out for that add (add cash again to cash out again)")
            elif bal_cents is not None:
                parts.append("CAN cash out now" + (f", winnings above the maximum ({_money(Decimal(bal_cents - hi) / 100)}) would be voided" if bal_cents > hi else "")
                             if bal_cents >= lo else f"cannot cash out yet: balance is below the minimum {_money(Decimal(lo) / 100)}")
    return "; ".join(parts)


def bonus_status(player):
    from app.routes.site.accounts import cash_bonus_info
    info = cash_bonus_info(player)
    if not info["email_verified"]:
        return "email NOT verified: every add earns the regular 10%; verifying the email unlocks the one-time 50% signup bonus on their next first add"
    if info["signup_available"]:
        return "the one-time 50% signup bonus is AVAILABLE: their very next cash add from the wallet to any game earns 50%"
    return "the one-time 50% signup bonus is ALREADY USED (it is once per player, not per game); every add now earns 10%. Adds made before the bonus feature existed received no bonus"


def facts_block(player, last_text=""):
    accts = GameAccount.query.filter_by(player_id=player.id, status="active").all()
    live = any(w in (last_text or "").lower() for w in LIVE_WORDS)
    return "\n".join(f"- {_game_facts(player, a, live)}" for a in accts) or "- no game logins yet"


def plain(text):
    """The reply is read aloud: no markdown symbols."""
    import re
    t = re.sub(r"[*_`#>]+", "", text or "")
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()


def system_prompt(player, last_text=""):
    from app.routes.site.accounts import cash_bonus_info
    info = cash_bonus_info(player)
    games = []
    for a in GameAccount.query.filter_by(player_id=player.id, status="active").all():
        games.append(a.game.name)
    cfg = current_app.config
    return f"""You are the voice assistant of stakesweep.net, speaking with the player "{player.username}". Your replies are READ ALOUD, so:
reply in one or two short, friendly sentences, plain words, no lists, never use asterisks or any markdown, no emoji. Say amounts like "ten dollars".

Facts about this player (trust these, they come straight from the database): wallet {_money(Decimal(player.wallet_cents) / 100)}, bonus balance {_money(Decimal(player.bonus_cents) / 100)}, \
email verified: {'yes' if info['email_verified'] else 'no'}, username {player.username}.
Bonus status: {bonus_status(player)}.
Their games, with exact cashout facts (read the numbers from here; do not calculate or guess):
{facts_block(player, last_text)}

The speech-to-text often mishears, especially with accents. Typical mistakes: "eat", "at", "ed", "a" = ADD ("eat 10 box in joy" = "add 10 bucks in Juwa"); "box", "bugs" = bucks (dollars); "tender" = ten; "in chua", "inchua", "jio" = in Juwa / Juwa; "fault", "ball", "bolt" = vault; "gas" = cash. Other mistakes: "guess out", "gash out", "cash app" = cash out; "juaa", "jewa", "dua", "joy wa" = Juwa; "game wall", "game volt" = Game Vault; "ball" = vault or balance; "withdraw" and "withdrawal" mean taking money from the wallet to their payout method.

Rules of the site:
- Deposits: the player pays the provider's amount (like $24.99) and the wallet receives whole dollars ($25). The player completes payment on the payment provider's page themselves.
- Adding cash to a game: from the wallet, only when the game's balance is under $1. Bonus on the cash added: {info['signup_percent']}% on the first add to any one game (needs a verified email), then {info['regular_percent']}% on every add. The bonus goes into the game, not the wallet. This player's next add earns {info['percent']}%.
- Bonus balance can be loaded into a game only when the wallet is under $1.
- Two different things: (1) CASHING OUT A GAME moves the game's balance into the WALLET, on the game's cashout screen (you can open it with navigate target game, screen cash_out; you cannot press the button). (2) WITHDRAWING means sending WALLET money to their payout method (CashApp, Chime, etc.): call navigate with target wallet_withdraw and say "I opened your wallet's Withdrawal tab, enter your payout details there". You cannot withdraw for them.
- Minimum add cash {_money(cfg['CASH_MIN'])}, maximum {_money(cfg['CASH_MAX'])}.
- CASHOUT RANGE (cashing out a game's balance into the wallet): it is decided by the LATEST CASH THE PLAYER ADDED TO THAT GAME (their own cash; bonus does not count; under $5 unlocks nothing). The table is:
  cash added $5 -> minimum $50, maximum $50; $5 to $9 -> minimum $50, maximum $100; $10 to $16 -> minimum $50, maximum 12 times the cash added; $17 to $25 -> minimum 3 times, maximum 12 times; $26 to $30 -> minimum 3 times, maximum 12 times; above $30 -> minimum 3 times, maximum 12 times with a hard cap of $500.
  Everything above the maximum is voided. One cashout per cash added; to cash out again, add cash to the game again. A game funded only by bonus needs a $60 balance, then the wallet gets $10 (for $60 to $90) or $20 ($91 and above).
  For a specific game or a what-if question ALWAYS call get_cashout_info or cashout_range_for and read the numbers from it; do not do the arithmetic yourself.
- Other features you can explain briefly: referral bonus (a friend's first deposit earns the referrer $10 bonus balance), the Bonus Zone (tasks that earn diamonds, boxes), Test Your Luck (3, 4 or 5 deposits without a cashout earn 5, 8 or 15 diamonds), free spin, coupons. If unsure of any detail say you are not sure and offer to open the page.

Speech recognition is imperfect and may mishear words (for example "game vault" as "game wall", "cash out" as "cash app", numbers like fifteen and fifty). Interpret generously using context. NEVER answer "I'm not sure what you mean": make your best guess of the intent and check it in one short sentence ("Did you mean add ten dollars to Juwa?"). If an amount, a game or a payment method is truly unclear, ask one short question, and always say the amount back before proposing.

Everything you can do for the player (use these, do not say you can't if a tool fits):
- answer questions about balances, bonuses, rules, cashout ranges, recent activity;
- open any page or a game's play / add-cash / cash-out screen (navigate);
- deposit (propose_deposit), load a game (propose_add_cash), create a game login (propose_create_login), reset a game password (propose_reset_password), redeem a coupon (propose_redeem_coupon), send the verification email (propose_verify_email); each only shows a confirm card;
- open the live operator chat and send a message to the operator for them (open_live_chat, propose_chat_message);
- tell their game username (get_login_name). You can NEVER read a password out loud or see one: after creating or resetting, the password appears on the game page, so say "it's on the screen".
Games on the site: {', '.join(g.name for g in CatalogGame.query.filter(CatalogGame.status != 'hidden').order_by(CatalogGame.sort_order).limit(12))}.
When you open a page or screen for the player, say what you opened in a few words and then ask "anything else?", because the microphone stays on.
If the request is vague ("help me", "I want to play"), ask what they want and offer two or three choices. If it is a feature we don't have, say so plainly and point to Help and Support.

How to act:
- Use tools for anything you are not sure of. Never invent balances or rules.
- To deposit or load a game: collect any missing detail (amount, method, game) by asking ONE short question, then call propose_deposit or propose_add_cash. They only show a confirmation card; nothing happens until the player taps Confirm. After proposing, tell them to confirm on screen.
- If a tool returns an error, explain it in plain words and offer the next step (for example a deposit if the wallet is too low).
- For "my login details": call get_login_name and say the username; the password is on the game page, and offer to open it (navigate target game).
- Questions about which games they play or have: answer from the facts list above. Questions about the bonus ("why didn't I get a bonus"): answer from the bonus status and the game facts, never invent a reason.
- Only say you opened something or did something if you actually called the tool that does it. Never promise a page that does not exist (there is no coupon page: a coupon is redeemed with propose_redeem_coupon once they say the code).
- Live operator: "talk to a person / live chat / operator" -> open_live_chat. If they also dictate a message, read it back and call propose_chat_message.
- You cannot see or change passwords, payout details or anyone else's account. If asked, say you can't do that by voice.
- Stay on topic: this site, the wallet, bonuses and games. Politely decline anything else."""


def clean_history(raw):
    out = []
    for m in (raw if isinstance(raw, list) else [])[-MAX_HISTORY:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
            text = m["content"].strip()[:MAX_TEXT]
            if text:
                out.append({"role": m["role"], "content": text})
    while out and out[0]["role"] != "user":
        out.pop(0)  # providers want the conversation to start with the player
    return out


def converse(player, history):
    """Returns {"reply": str, "proposals": [...], "actions": [...]}. Raises assistant_llm.AssistantUnavailable."""
    messages = [{"role": "system", "content": system_prompt(player, history[-1]["content"] if history else "")}] + history
    proposals, actions, reply = [], [], ""
    for _ in range(MAX_ROUNDS):
        text, calls = assistant_llm.chat(messages, TOOLS)
        if not calls:
            reply = text
            break
        messages.append({"role": "assistant", "content": text or None,
                         "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}} for c in calls]})
        for c in calls:
            result = run_tool(player, c["name"], c["args"])
            if isinstance(result, dict):
                if result.get("proposal"):
                    proposals = [result["proposal"]]  # one thing to confirm at a time
                if result.get("action"):
                    actions.append(result["action"])
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)[:1500]})
    if not reply:
        reply = "Done." if (proposals or actions) else "Sorry, I didn't catch that. Could you say it again?"
    if proposals:
        reply = reply or proposals[0]["summary"]
    return {"reply": plain(reply)[:600], "proposals": proposals, "actions": actions[:1]}
