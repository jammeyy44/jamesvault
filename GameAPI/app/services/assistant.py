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
     "parameters": {"type": "object", "properties": {"cash_added": {"type": "number", "description": "Dollars of the player's own cash added to the game"}}, "required": ["cash_added"]}},
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
    {"name": "navigate", "description": "Open a part of the website for the player.",
     "parameters": {"type": "object", "properties": {
         "target": {"type": "string", "enum": ["home", "games", "wallet", "bonus_zone", "refer", "support", "dashboard", "cashout_rules", "game"]},
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


def t_cashout_range_for(player, cash_added):
    from app.services import cashout_rules as rules
    a = _amount(cash_added)
    if a is None:
        return {"error": "I need a dollar amount."}
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


def t_navigate(player, target, game=None, screen="play"):
    if target == "wallet":
        return {"action": {"type": "open_wallet"}}
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
            return t_cashout_range_for(player, args.get("cash_added"))
        if name == "list_deposit_methods":
            return t_list_deposit_methods(player)
        if name == "propose_deposit":
            return t_propose_deposit(player, args.get("amount"), args.get("method"))
        if name == "propose_add_cash":
            return t_propose_add_cash(player, args.get("game"), args.get("amount"), args.get("source") or "wallet")
        if name == "navigate":
            return t_navigate(player, args.get("target"), args.get("game"), args.get("screen") or "play")
    except Exception:
        logger.exception("assistant tool %s failed", name)
        return {"error": "That didn't work. Please try again."}
    return {"error": "Unknown tool."}


# ------------------------------------------------------------------ prompt + loop
def system_prompt(player):
    from app.routes.site.accounts import cash_bonus_info
    info = cash_bonus_info(player)
    games = []
    for a in GameAccount.query.filter_by(player_id=player.id, status="active").all():
        games.append(a.game.name)
    cfg = current_app.config
    return f"""You are the voice assistant of stakesweep.net, speaking with the player "{player.username}". Your replies are READ ALOUD, so:
reply in one or two short, friendly sentences, plain words, no lists, no markdown, no emoji. Say amounts like "ten dollars".

Facts about this player (trust these): wallet {_money(Decimal(player.wallet_cents) / 100)}, bonus balance {_money(Decimal(player.bonus_cents) / 100)}, \
email verified: {'yes' if info['email_verified'] else 'no'}, games with a login: {', '.join(games) or 'none yet'}.

Rules of the site:
- Deposits: the player pays the provider's amount (like $24.99) and the wallet receives whole dollars ($25). The player completes payment on the payment provider's page themselves.
- Adding cash to a game: from the wallet, only when the game's balance is under $1. Bonus on the cash added: {info['signup_percent']}% on the first add to any one game (needs a verified email), then {info['regular_percent']}% on every add. The bonus goes into the game, not the wallet. This player's next add earns {info['percent']}%.
- Bonus balance can be loaded into a game only when the wallet is under $1.
- Cashing out needs the game's cashout screen; you can open it but you cannot cash out yourself. Withdrawals to a payout method are done in the wallet.
- Minimum add cash {_money(cfg['CASH_MIN'])}, maximum {_money(cfg['CASH_MAX'])}.
- CASHOUT RANGE (cashing out a game's balance into the wallet): it is decided by the LATEST CASH THE PLAYER ADDED TO THAT GAME (their own cash; bonus does not count; under $5 unlocks nothing). The table is:
  cash added $5 -> minimum $50, maximum $50; $5 to $9 -> minimum $50, maximum $100; $10 to $16 -> minimum $50, maximum 12 times the cash added; $17 to $25 -> minimum 3 times, maximum 12 times; $26 to $30 -> minimum 3 times, maximum 12 times; above $30 -> minimum 3 times, maximum 12 times with a hard cap of $500.
  Everything above the maximum is voided. One cashout per cash added; to cash out again, add cash to the game again. A game funded only by bonus needs a $60 balance, then the wallet gets $10 (for $60 to $90) or $20 ($91 and above).
  For a specific game or a what-if question ALWAYS call get_cashout_info or cashout_range_for and read the numbers from it; do not do the arithmetic yourself.
- Other features you can explain briefly: referral bonus (a friend's first deposit earns the referrer $10 bonus balance), the Bonus Zone (tasks that earn diamonds, boxes), Test Your Luck (3, 4 or 5 deposits without a cashout earn 5, 8 or 15 diamonds), free spin, coupons. If unsure of any detail say you are not sure and offer to open the page.

Speech recognition is imperfect and may mishear words (for example "game vault" as "game wall", "cash out" as "cash app", numbers like fifteen and fifty). Interpret generously using context. If an amount, a game or a payment method is unclear, ask a short question instead of guessing, and always say the amount back before proposing.

How to act:
- Use tools for anything you are not sure of. Never invent balances or rules.
- To deposit or load a game: collect any missing detail (amount, method, game) by asking ONE short question, then call propose_deposit or propose_add_cash. They only show a confirmation card; nothing happens until the player taps Confirm. After proposing, tell them to confirm on screen.
- If a tool returns an error, explain it in plain words and offer the next step (for example a deposit if the wallet is too low).
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
    messages = [{"role": "system", "content": system_prompt(player)}] + history
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
    return {"reply": reply[:600], "proposals": proposals, "actions": actions[:1]}
