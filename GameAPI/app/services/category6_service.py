"""
Agent API adapter (Game Vault, Vegas Sweeps): the providers' signed "external" API, no login page and no CAPTCHA.

Every request is multipart/form-data to {base_url}/api/external/<action> and carries agent_id, timestamp and
token = MD5("agent_id:timestamp:secret_key").upper(). In Admin -> Providers: Username = the agent ID, Password = the secret key.
The provider only accepts calls from IP addresses it has whitelisted (status 5), so the server's IP must be given to them.
"""
import hashlib
import random
import time

import requests

from .base_service import BaseGameService

STATUS = {
    1: "Invalid agent ID", 2: "Invalid request parameters", 3: "Invalid token", 4: "Token expired",
    5: "Access IP is not whitelisted (ask the provider to whitelist this server's IP address)",
    6: "Insufficient agent balance", 7: "Insufficient user balance", 8: "Invalid user ID", 9: "User account frozen",
    10: "User is in game", 11: "Invalid amount", 12: "Recharge failed", 13: "Recharge permission denied",
    14: "Withdrawal failed", 15: "Withdrawal amount exceeds daily limit", 16: "Withdrawal under review",
    17: "Withdrawal permission denied", 18: "Account name format error (letters, numbers, underscores)",
    19: "Agent has no register-user permission", 20: "Account name already exists", 21: "System failed",
    22: "Number of registrations from this IP exceeds the limit", 23: "Password must be 6 to 32 characters",
    400: "Parameter error",
}


class Category6Service(BaseGameService):
    """Service for providers that expose the signed agent API."""

    TIMEOUT = 20

    # (timestamp in milliseconds?, uppercase token?). The documents disagree (Game Vault: 13 digits + "uppercase"; Juwa: 10
    # digits + lowercase) and the example tokens in them are lowercase hex. Production use of this API shows lowercase
    # tokens with a millisecond timestamp working, so that is tried first; if the provider answers "invalid token" /
    # "token expired", the other combinations are tried and the one that works is kept.
    STYLES = [(True, False), (False, False), (True, True), (False, True)]

    def __init__(self, provider):
        super().__init__(provider)
        self._styles = list(self.STYLES)
        if "juwa" in str(provider.name).lower():
            self._styles = [(False, False), (True, False), (False, True), (True, True)]
        self._ms, self._upper = self._styles[0]

    def _stamp(self):
        return str(int(time.time() * 1000)) if self._ms else str(int(time.time()))

    def _signed(self, params):
        agent_id, secret = str(self.provider.username), str(self.provider.password)
        stamp = self._stamp()
        token = hashlib.md5(f"{agent_id}:{stamp}:{secret}".encode()).hexdigest()
        token = token.upper() if self._upper else token.lower()
        fields = {"agent_id": agent_id, "timestamp": stamp, "token": token, **{k: str(v) for k, v in params.items()}}
        return {k: (None, v) for k, v in fields.items()}  # forces multipart/form-data

    def _post(self, action, params=None, _style=0):
        """POST one signed call. Returns {"data": ...} on success or {"error": "<reason>"}. Network errors propagate
        (the caller treats a money movement that errors out as 'outcome unknown', never as a clean failure)."""
        url = f"{self.provider.base_url.rstrip('/')}/api/external/{action}"
        response = requests.post(url, files=self._signed(params or {}), headers={"Accept": "application/json"}, timeout=self.TIMEOUT)
        try:
            body = response.json()
        except ValueError:
            return {"error": f"unexpected response (HTTP {response.status_code})"}
        code = body.get("code")
        if code == 0:
            return {"data": body.get("data") or {}}
        if code in (3, 4) and _style + 1 < len(self._styles):  # token refused: try the next documented style
            previous = (self._ms, self._upper)
            self._ms, self._upper = self._styles[_style + 1]
            result = self._post(action, params, _style + 1)
            if "error" in result:
                self._ms, self._upper = previous
            return result
        return {"error": f"{code}: {STATUS.get(code, body.get('msg') or 'request failed')}"}

    # -- the interface the gateway uses (same as the other adapters) -------------------------------------------------
    def login(self, username=None, password=None, **_):
        """There is no session: this checks the agent ID and secret by asking for the agent balance."""
        result = self._post("agentBalance")
        if "error" in result:
            return {"message": "Login failed", "error": result["error"]}
        return {"message": "Login successful"}

    def _user_id(self, username):
        result = self._post("getUserID", {"account_name": username})
        if "error" in result:
            return None, result["error"]
        uid = result["data"].get("user_id")
        return (str(uid), None) if uid else (None, "User not found")

    def add_user(self, username, password):
        result = self._post("addUser", {"account": username, "login_pwd": password})
        if "error" in result:
            return {"message": "Failed to add user", "error": result["error"]}
        return {"message": "User created", "username": username}

    def get_balances(self, username):
        uid, err = self._user_id(username)
        if not uid:
            return {"message": "User not found", "error": err}
        result = self._post("userBalance", {"user_id": uid})
        if "error" in result:
            return {"message": "Failed to fetch balance", "error": result["error"]}
        return {"message": "Balance fetched", "balance": result["data"].get("user_balance")}

    def get_agent_balance(self):
        result = self._post("agentBalance")
        if "error" in result:
            return {"message": "Failed to fetch agent balance", "error": result["error"]}
        return {"message": "Agent balance fetched", "balance": result["data"].get("agent_balance")}

    @staticmethod
    def _order_id():
        return f"{int(time.time() * 1000)}{random.randint(100, 999)}"  # unique per call; never reused on a retry

    def _move(self, action, username, amount):
        uid, err = self._user_id(username)
        if not uid:
            return {"message": "User not found", "error": err}
        # No automatic retry here: a timeout after the provider accepted the call must not be sent again with a new order id.
        result = self._post(action, {"user_id": uid, "amount": f"{amount:g}" if float(amount).is_integer() else f"{amount:.2f}",
                                     "order_id": self._order_id()})
        if "error" in result:
            return {"message": f"Failed to {action}", "error": result["error"]}
        return {"message": "ok"}

    def recharge(self, username, amount):
        return self._move("recharge", username, float(amount))

    def redeem(self, username, amount):
        return self._move("withdraw", username, float(amount))

    def change_password(self, username, new_password):
        uid, err = self._user_id(username)
        if not uid:
            return {"message": "User not found", "error": err}
        result = self._post("resetPassword", {"user_id": uid, "login_pwd": new_password})
        if "error" in result:
            return {"message": "Failed to change password", "error": result["error"]}
        return {"message": "Password changed successfully"}
