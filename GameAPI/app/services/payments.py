"""
Payment provider client (Paydora Payment API; base URL and keys come from config/env, never from code).

* PaydoraClient: real HTTPS client. Sends `Authorization: Bearer <key>` and an `Idempotency-Key` on every order
  creation so a retry replays the original order instead of creating a second one.
* SandboxPayments: development only (JV_SANDBOX). Orders are fake and clearly flagged; refused in production.

Error model: PaymentError(definitive=True) means the provider answered with a 4xx - nothing was created.
definitive=False (timeouts, 5xx, 409, malformed answers) means the outcome is UNKNOWN; for money going out the
caller must hold the funds and reconcile, never assume failure.
"""
import logging
import secrets

import requests
from flask import current_app

logger = logging.getLogger("jamesvault.payments")

# Amounts the provider accepts per method (Payment API doc, section 3.1). Only these values are accepted; nothing is
# rounded. Methods not listed here accept any amount the provider allows (its own error is shown to the player).
ACCEPTED_AMOUNTS = {
    "cashapp": [9.99, 14.99, 19.99, 24.99, 29.99, 39.99, 49.99, 59.99, 99.99, 124.99, 149.99, 199.99],
    "applepay": [9.99, 14.99, 19.99, 24.99, 29.99, 39.99, 49.99, 59.99, 99.99, 124.99, 149.99, 199.99],
    "googlepay": [9.99, 14.99, 19.99, 24.99, 29.99, 39.99, 49.99, 59.99, 99.99, 124.99, 149.99, 199.99],
    "card": [10.99, 11.99, 12.99, 13.99, 14.99, 17.99, 19.99, 24.99, 29.99, 30.99, 39.99, 49.99, 59.99, 99.99,
             124.99, 129.99, 149.99, 199.99],
    "chime": [20, 25, 30, 31, 40, 50, 60, 100, 125, 130, 150, 200, 300, 400, 500],
}
# Withdrawal destinations we collect. Card payouts are deliberately NOT supported: we never handle card numbers.
PAYOUT_FIELDS = {"cashapp": "cashtag", "chime": "Chime tag", "zelle": "phone or email", "paypal": "PayPal email",
                 "venmo": "Venmo username"}


class PaymentError(Exception):
    """Message is safe to show to players."""

    def __init__(self, message, definitive=False, detail=None):
        super().__init__(message)
        self.definitive = definitive
        self.detail = detail  # the provider's own HTTP status / message: for staff and logs, never for players


def normalize_value(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


class PaydoraClient:
    name = "live"

    def __init__(self):
        cfg = current_app.config
        self.base = cfg["PAYDORA_BASE_URL"].rstrip("/")
        self.key = cfg["PAYDORA_API_KEY"]
        if not self.key:
            raise PaymentError("Payments are not configured.", definitive=True)

    def _request(self, method, path, json=None, idempotency_key=None, timeout=15):
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            r = requests.request(method, f"{self.base}{path}", json=json, headers=headers, timeout=timeout,
                                 allow_redirects=False)
        except requests.RequestException as e:
            logger.error("payment provider unreachable on %s %s: %s", method, path, type(e).__name__)
            raise PaymentError("The payment service is unavailable right now. Please try again later.") from e
        try:
            body = r.json() if r.content else {}
        except ValueError:
            body = {}
        if r.status_code in (200, 201, 204):
            return body
        provider_msg = (body.get("message") if isinstance(body, dict) else None) or ""
        logger.warning("payment provider %s %s -> %s %s", method, path, r.status_code, provider_msg[:200])
        detail = f"HTTP {r.status_code}: {provider_msg[:160]}".strip()
        if r.status_code in (400, 404, 422):
            # Validation-type refusals are safe to show (e.g. accepted amounts); nothing was created.
            raise PaymentError(provider_msg[:300] or "The payment was not accepted.", definitive=True, detail=detail)
        if r.status_code in (401, 403):
            raise PaymentError("The payment service is not available right now.", definitive=True, detail=detail)
        raise PaymentError("The payment service is busy. Please try again in a moment.", detail=detail)  # 409/429/5xx: unknown

    def methods(self):
        data = self._request("GET", "/payment-methods")
        return {"deposits": data.get("deposits", []), "withdrawals": data.get("withdrawals", [])}

    def create_deposit(self, *, method_id, amount, customer_ip, device_fingerprint, user_name, return_url,
                       user_agent, idempotency_key):
        body = {"paymentMethodId": method_id, "amount": float(amount), "customerIp": customer_ip,
                "deviceFingerprint": device_fingerprint, "userName": user_name}
        if return_url:
            body["returnUrl"] = return_url
        if user_agent:
            body["customerUserAgent"] = user_agent[:1000]
        return self._request("POST", "/deposits/create", body, idempotency_key)

    def get_deposit(self, deposit_id):
        return self._request("GET", f"/deposits/{deposit_id}")

    def get_withdrawal(self, withdrawal_id):
        return self._request("GET", f"/withdrawals/{withdrawal_id}")

    def create_withdrawal(self, *, method_id, amount, address, user_name, chime_name, idempotency_key):
        body = {"paymentMethodId": method_id, "amount": float(amount), "address": address, "userName": user_name}
        if chime_name:
            body["chimePhoneEmail"] = chime_name
        return self._request("POST", "/withdrawals/create", body, idempotency_key)


class SandboxPayments:
    """Development stand-in. Deposits are 'paid' immediately; payouts complete immediately. Never in production."""
    name = "sandbox"

    def __init__(self):
        if current_app.config.get("JV_ENV") == "production":
            raise RuntimeError("Sandbox payments must not run in production")

    def methods(self):
        dep = [("cashapp", "CashApp"), ("chime", "Chime"), ("applepay", "Apple Pay"), ("googlepay", "Google Pay"), ("paypal", "PayPal")]
        wd = [("cashapp", "CashApp"), ("chime", "Chime"), ("paypal", "PayPal"), ("venmo", "Venmo"), ("zelle", "Zelle")]
        return {"deposits": [{"id": f"sbx-d-{v}", "value": v, "name": n} for v, n in dep],
                "withdrawals": [{"id": f"sbx-w-{v}", "value": v, "name": n} for v, n in wd]}

    def create_deposit(self, **kw):
        return {"id": f"sbx{secrets.token_hex(8)}", "referenceId": f"SBX-{secrets.token_hex(3).upper()}",
                "status": "paid", "paymentUrl": None, "isChimney": False}

    def get_deposit(self, deposit_id):
        return {"id": deposit_id, "status": "paid"}

    def create_withdrawal(self, **kw):
        return {"id": f"sbx{secrets.token_hex(8)}", "referenceId": f"SBX-{secrets.token_hex(3).upper()}",
                "status": "confirmed"}


def payments_mode():
    """live (a real Paydora key is set), sandbox (no key AND JV_SANDBOX is on: development only) or disabled.
    A missing or mistyped key can never silently turn a real site into a fake-payments one."""
    cfg = current_app.config
    f = cfg["FEATURES"]
    if not f.get("wallet"):
        return "disabled"
    if cfg.get("PAYDORA_API_KEY"):
        return "live"
    return "sandbox" if f.get("sandbox") else "disabled"


def get_payments():
    mode = payments_mode()
    if mode == "disabled":
        return None
    if mode == "live":
        return PaydoraClient()
    return SandboxPayments()

