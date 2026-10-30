"""
Gateways between the site and a game provider's agent panel.

* SandboxGateway: development only. Clearly labelled in the UI; accounts and balances exist only in our
  database. It refuses to run when JV_ENV=production.
* ProviderGateway: wraps the existing Category 1-5 adapters. UNVERIFIED against live panels; it is only used
  when JV_ENABLE_GAME_ACCOUNTS=true and sandbox is off. Failures are reported honestly, never faked.
"""
import logging
import re
import secrets
from decimal import Decimal, InvalidOperation

from flask import current_app

logger = logging.getLogger("jamesvault.gateway")


class GatewayError(Exception):
    """Raised with a message that is safe to show to players."""


class AmbiguousOutcome(Exception):
    """The provider call failed in a way that does not prove it had no effect (timeout, crash mid-request).
    Money operations hitting this must be reconciled by hand, never blindly retried."""


def make_credentials(game_name):
    prefix = (re.sub(r'[^a-z]', '', game_name.lower())[:2] or "jv")
    username = f"{prefix}{secrets.randbelow(900000) + 100000}"
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    password = "".join(secrets.choice(alphabet) for _ in range(10))
    return username, password


class SandboxGateway:
    name = "sandbox"

    def __init__(self):
        if current_app.config.get("JV_ENV") == "production":
            raise RuntimeError("Sandbox gateway must not run in production")

    def create_account(self, game, username, password):
        return {"username": username}

    def get_balance(self, account):
        from app.models_site import CashRequest, RedeemRequest
        rows = CashRequest.query.filter_by(game_account_id=account.id, status='completed').all()
        taken = RedeemRequest.query.filter_by(game_account_id=account.id, status='completed').all()
        return sum((r.amount for r in rows), Decimal("0.00")) - sum((Decimal(r.balance_cents) / 100 for r in taken), Decimal("0.00"))

    def recharge(self, account, amount):
        return None  # the completed CashRequest row is the sandbox ledger

    def redeem(self, account, amount):
        return None  # the completed RedeemRequest row is the sandbox ledger

    def reset_password(self, account, new_password):
        return None  # the stored (encrypted) password is the sandbox account


# The games each adapter family is known to serve (from the original provider documentation). The admin panel shows
# these names instead of "CATEGORY1" etc., merged with the names of providers actually configured in the database.
FAMILY_GAMES = {
    "CATEGORY1": ["Gameroom", "Cash Machine", "Mr All In One", "Cash Frenzy", "Mafia", "King of Pop"],
    "CATEGORY2": [],  # old captcha panel login; no game uses it now
    "CATEGORY3": ["Orion Stars", "Panda Master", "Milkyway", "Fire Kirin"],
    "CATEGORY4": ["River Sweeps"],
    "CATEGORY5": ["Vblink", "Egame", "Ultra Panda"],
    "CATEGORY6": ["Game Vault", "Vegas Sweeps", "Juwa", "Juwa 2.0"],
    "VBLINK": ["Vblink (legacy entry; use the family with Egame and Ultra Panda)"],
}


def adapter_families(configured=None):
    """[{value, label, games}] for the adapter-family dropdown. `configured` = [(category_value, provider_name)]."""
    extra = {}
    for category, name in configured or []:
        extra.setdefault(category, []).append(name)
    out = []
    for value, games in FAMILY_GAMES.items():
        names = list(games)
        for n in extra.get(value, []):
            if n.lower() not in {g.lower() for g in names}:
                names.append(n)
        out.append({"value": value, "label": value.replace("CATEGORY", "Category "), "games": names})
    return out


class ProviderGateway:
    name = "live"

    # Adapter family per Provider.category. To support a new family: write an adapter class with the same
    # methods as the existing services (login / add_user / get_balances / recharge / get_agent_balance),
    # register it here, add the category to RemoteProvider, then add provider rows in Admin -> Providers.
    SERVICES = {
        "CATEGORY1": "app.services.category1_service.Category1Service",
        "CATEGORY2": "app.services.category2_service.Category2Service",
        "CATEGORY3": "app.services.category3_service.Category3Service",
        "CATEGORY4": "app.services.category4_service.Category4Service",
        "CATEGORY5": "app.services.category5_service.Category5Service",
        "CATEGORY6": "app.services.category6_service.Category6Service",
    }

    @staticmethod
    def _log(provider, action, ok, detail=None, started=None):
        """Record one provider call. Never stores credentials or request bodies."""
        try:
            import time as _t
            from app import db
            from app.models_site import ProviderLog
            ms = int((_t.monotonic() - started) * 1000) if started else None
            db.session.add(ProviderLog(provider_id=provider.id if provider else None, action=action, success=ok,
                                       detail=(str(detail)[:240] if detail else None), duration_ms=ms))
            db.session.commit()
        except Exception:
            logger.exception("could not write provider log")

    def _service(self, provider):
        import importlib
        if provider is None or provider.category.name not in self.SERVICES:
            raise GatewayError("This game is not connected to a provider yet.")
        if not provider.is_active:
            # An admin switched this provider off: send it no traffic at all.
            raise GatewayError("This game is temporarily unavailable. Please try again later.")
        module, cls = self.SERVICES[provider.category.name].rsplit(".", 1)
        service = getattr(importlib.import_module(module), cls)(provider)
        login = service.login(provider.username, provider.password)
        if isinstance(login, dict) and login.get("error"):
            err = GatewayError("The game provider is unavailable right now. Please try again later.")
            err.reason = str(login.get("error"))[:200]  # for admins only; never shown to players
            raise err
        return service

    def _call(self, provider, action, fn):
        """Run fn(service); translate adapter errors into GatewayError and log the outcome."""
        import time as _t
        started = _t.monotonic()
        try:
            service = self._service(provider)
            result = fn(service)
            if not isinstance(result, dict) or result.get("error"):
                err = result.get("error") if isinstance(result, dict) else "unexpected response"
                self._log(provider, action, False, err, started)
                failure = GatewayError("The game provider could not complete that request. Please try again later.")
                failure.reason = str(err)[:200]  # the provider's own reason (for admins and for "player not found" checks)
                raise failure
            self._log(provider, action, True, None, started)
            return result
        except GatewayError as e:
            if str(e).startswith(("This game", "The game provider is unavailable")):
                self._log(provider, action, False, getattr(e, "reason", None) or str(e), started)
            raise
        except Exception as e:
            # Outcome unknown (timeout, crash mid-call): callers must treat money operations as ambiguous.
            self._log(provider, action, False, f"{type(e).__name__}: {e}", started)
            raise AmbiguousOutcome(str(e)) from e

    @staticmethod
    def _known(s, account):
        """Hand the saved provider player id to adapters that can use it (skips a lookup that may fail)."""
        if getattr(account, "provider_user_id", None):
            s.known_ids = {account.provider_username: account.provider_user_id}
        return s

    def create_account(self, game, username, password):
        # The login only exists once the provider has really created it. Any failure is raised to the caller, never hidden.
        return self._call(game.provider, "add_user", lambda s: s.add_user(username, password))

    def get_balance(self, account):
        result = self._call(account.game.provider, "get_balances", lambda s: self._known(s, account).get_balances(account.provider_username))
        try:
            return Decimal(str(result.get("balance")).replace("$", "").replace(",", "").strip())
        except (InvalidOperation, TypeError):
            raise GatewayError("The game provider returned an unreadable balance.")

    def recharge(self, account, amount):
        self._call(account.game.provider, "recharge", lambda s: self._known(s, account).recharge(account.provider_username, float(amount)))

    def reset_password(self, account, new_password):
        """Set a new password on the player's login at the provider."""
        self._call(account.game.provider, "change_password", lambda s: self._known(s, account).change_password(account.provider_username, new_password))

    def redeem(self, account, amount):
        """Take `amount` (the player's whole balance) out of the game account."""
        self._call(account.game.provider, "redeem", lambda s: self._known(s, account).redeem(account.provider_username, float(amount)))

    def test_connection(self, provider):
        """Admin check: can we log in, and what is the agent balance (the funds available to recharge players)."""
        result = {"ok": False, "agent_balance": None, "message": None}
        try:
            result_login = self._call(provider, "test_login", lambda s: {"ok": True})
            result["ok"] = bool(result_login)
        except GatewayError as e:
            reason = getattr(e, "reason", None)
            result["message"] = f"{e} ({reason})" if reason else str(e)
            return result
        except AmbiguousOutcome as e:
            result["message"] = f"Connection error: {str(e)[:120]}"
            return result
        try:
            bal = self._call(provider, "agent_balance", lambda s: s.get_agent_balance())
            result["agent_balance"] = str(bal.get("balance")) if bal.get("balance") is not None else None
        except Exception:
            result["message"] = "Logged in, but the agent balance could not be read."
        return result


def get_gateway():
    """Returns the active gateway, or None when game accounts are not enabled."""
    features = current_app.config["FEATURES"]
    if features["sandbox"]:
        return SandboxGateway()
    if features["game_accounts"]:
        return ProviderGateway()
    return None
