"""
Service class for Category 2 game providers (e.g., Game Vault).
Handles CAPTCHA solving and token-based authentication.
"""
# app/services/category2_service.py
import random
import time
from .base_service import BaseGameService


class Category2Service(BaseGameService):
    """Service for Category 2 providers."""

    def _generate_t_value(self):
        """Generate a random 8-digit number for CAPTCHA."""
        return random.randint(10000000, 99999999)

    def solve_captcha(self):
        t_value = self._generate_t_value()
        captcha_url = f"{self.base_url}/api/agent/captcha?t={t_value}"
        self.logger.info(f"[{self.provider.name}] Fetching CAPTCHA from: {captcha_url}")
        try:
            code = self.solve_image_captcha(captcha_url)
            self.logger.info(f"[{self.provider.name}] CAPTCHA solved")
            return code, t_value
        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"[{self.provider.name}] CAPTCHA solving failed: {e}")
            return None, t_value  # Return tuple to avoid unpacking error

    @BaseGameService.retry_on_failure()
    def login(self, username, password, max_retries=3, retry_delay=3):
        """Log in using provider credentials and the image CAPTCHA (needs CAPTCHA_API_KEY)."""
        for attempt in range(max_retries):
            try:
                agent_code, t_value = self.solve_captcha()
                if not agent_code:
                    continue
                payload = {
                    "agent_name": username,
                    "agent_pwd": password,
                    "agent_code": agent_code,
                    "t": t_value,
                }
                response = self._make_request("POST", "/api/agent/agentLogin", data=payload)
                if response.ok:
                    data = response.json()
                    if data.get("msg") == "success":
                        token = data["data"]["token"]
                        self.session.headers["Authorization"] = f"Bearer {token}"
                        self._save_cached_data()
                        self.logger.info(f"[{self.provider.name}] Login successful")
                        return {"message": "Login successful", "token": token}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Login error: {e}")
            time.sleep(retry_delay)
        self.logger.error(f"[{self.provider.name}] Max login attempts reached")
        return {"message": "Login failed", "error": getattr(self, "last_error", None) or "Max attempts reached"}

    @BaseGameService.retry_on_failure()
    def add_user(self, username, password):
        """Add a new user to the provider."""
        payload = {
            "account": username,
            "login_pwd": password,
            "check_pwd": password,
        }
        response = self._make_request("POST", "/api/user/addUser", json=payload)
        if response.ok:
            data = response.json()
            if data.get("msg") == "success":
                self.logger.info(f"[{self.provider.name}] User {username} added successfully")
                return {"message": "User created", "username": username}
            return {"message": "Failed to add user", "error": data.get("msg")}
        return {"message": "Failed to add user", "error": response.text}

    @BaseGameService.retry_on_failure()
    def recharge(self, username, amount):
        """Recharge a user's account."""
        user_id_response = self._search_user(username)
        if not user_id_response["user_id"]:
            return {"message": "User not found", "error": user_id_response["error"]}
        payload = {"user_id": user_id_response["user_id"], "type": 1, "amount": amount}
        response = self._make_request("POST", "/api/user/rechargeRedeem", json=payload)
        if response.ok:
            data = response.json()
            if data.get("msg") == "success":
                self.logger.info(f"[{self.provider.name}] Recharge successful for {username}")
                return {"message": "Recharged successfully"}
            return {"message": "Failed to recharge", "error": data.get("msg")}
        return {"message": "Failed to recharge", "error": response.text}

    @BaseGameService.retry_on_failure()
    def redeem(self, username, amount):
        """Redeem funds from a user's account."""
        user_id_response = self._search_user(username)
        if not user_id_response["user_id"]:
            return {"message": "User not found", "error": user_id_response["error"]}
        payload = {"user_id": user_id_response["user_id"], "type": 2, "amount": amount}
        response = self._make_request("POST", "/api/user/rechargeRedeem", json=payload)
        if response.ok:
            data = response.json()
            if data.get("msg") == "success":
                self.logger.info(f"[{self.provider.name}] Redeem successful for {username}")
                return {"message": "Redeemed successfully"}
            return {"message": "Failed to redeem", "error": data.get("msg")}
        return {"message": "Failed to redeem", "error": response.text}

    @BaseGameService.retry_on_failure()
    def change_password(self, username, new_password):
        """Change a user's password."""
        user_id_response = self._search_user(username)
        if not user_id_response["user_id"]:
            return {"message": "User not found", "error": user_id_response["error"]}
        payload = {"uid": user_id_response["user_id"], "login_pwd": new_password, "check_pwd": new_password}
        response = self._make_request("POST", "/api/user/resetUserPwd", json=payload)
        if response.ok:
            data = response.json()
            if data.get("msg") == "success":
                self.logger.info(f"[{self.provider.name}] Password changed for {username}")
                return {"message": "Password changed successfully"}
            return {"message": "Failed to change password", "error": data.get("msg")}
        return {"message": "Failed to change password", "error": response.text}

    @BaseGameService.retry_on_failure()
    def get_balances(self, username):
        """Fetch user balance."""
        user_id_response = self._search_user(username)
        if not user_id_response["user_id"]:
            return {"message": "User not found", "error": user_id_response["error"]}
        payload = {"user_id": user_id_response["user_id"]}
        response = self._make_request("POST", "/api/user/balance", json=payload)
        if response.ok:
            data = response.json()
            if data.get("msg") == "success":
                self.logger.info(f"[{self.provider.name}] Balance fetched for {username}")
                return {"message": "Balance fetched", "balance": data["data"]["t"]}
            return {"message": "Failed to fetch balance", "error": data.get("msg")}
        return {"message": "Failed to fetch balance", "error": response.text}

    @BaseGameService.retry_on_failure()
    def get_agent_balance(self):
        """Fetch agent's balance."""
        agent_id = self._get_agent_id()
        if not agent_id:
            return {"message": "Failed to fetch agent balance", "error": "No agent ID"}
        payload = {"agent_id": agent_id}
        response = self._make_request("POST", "/api/agent/balance", json=payload)
        if response.ok:
            data = response.json()
            if data.get("msg") == "success":
                self.logger.info(f"[{self.provider.name}] Agent balance fetched")
                return {"message": "Agent balance fetched", "balance": data["data"]["t"]}
            return {"message": "Failed to fetch agent balance", "error": data.get("msg")}
        return {"message": "Failed to fetch agent balance", "error": response.text}

    @BaseGameService.retry_on_failure()
    def _search_user(self, username):
        """Search for a user by username."""
        payload = {"type": 1, "search": username}
        response = self._make_request("POST", "/api/user/userList", json=payload)
        if response.ok:
            data = response.json()
            if data.get("msg") == "success" and data["data"]["list"]:
                return {"user_id": data["data"]["list"][0]["user_id"], "error": None}
            return {"user_id": None, "error": "User not found"}
        return {"user_id": None, "error": "Server unreachable"}

    def _get_agent_id(self):
        """Get the agent ID."""
        if hasattr(self, 'agent_id') and self.agent_id:
            return self.agent_id
        response = self._make_request("POST", "/api/agent/agentList")
        if response.ok:
            data = response.json()
            if data.get("msg") == "success":
                self.agent_id = data["data"]["list"][0]["agent_id"]
                return self.agent_id
        self.logger.error(f"[{self.provider.name}] Failed to fetch agent ID")
        return None
