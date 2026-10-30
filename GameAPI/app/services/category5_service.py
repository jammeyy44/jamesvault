"""
Service class for Category 5 game providers
Handles web page interactions and form submissions.
"""

# app/services/category5_service.py
import time
from twocaptcha import TwoCaptcha
from config import Config
from .base_service import BaseGameService
from .category4_service import Category4Service  # Category4Service is updated without encryption

class Category5Service(Category4Service):
    CAPTCHA_API_KEY = Config.CAPTCHA_API_KEY

    def _solve_cloudflare_captcha(self, response):
        if "Cloudflare" not in response.text:
            return None
        self.logger.info(f"[{self.provider.name}] Encountered Cloudflare CAPTCHA")
        try:
            solver = TwoCaptcha(self.CAPTCHA_API_KEY)
            # Extract site key from Cloudflare page if needed (simplified here)
            site_key = "some_site_key"  # Replace with actual extraction logic if available
            result = solver.hcaptcha(sitekey=site_key, url=self.base_url)
            self.logger.info(f"[{self.provider.name}] Cloudflare CAPTCHA solved: {result['code']}")
            return result['code']
        except Exception as e:
            self.logger.error(f"[{self.provider.name}] CAPTCHA solving failed: {e}")
            return None

    def login(self, username, password, max_retries=3, retry_delay=2):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        self.session.headers.update(headers)
        for attempt in range(max_retries):
            try:
                payload = {
                    "username": username,
                    "password": password,
                    "auth_code": "",
                }
                response = self._make_request("POST", "/api/user/login", json=payload, timeout=20)
                self.logger.debug(f"[{self.provider.name}] Login response: {response.text[:500]}")
                if "Cloudflare" in response.text:
                    captcha_code = self._solve_cloudflare_captcha(response)
                    if captcha_code:
                        payload["auth_code"] = captcha_code
                        response = self._make_request("POST", "/api/user/login", json=payload, timeout=20)
                    else:
                        self.logger.error(f"[{self.provider.name}] Blocked by Cloudflare, retrying...")
                        time.sleep(retry_delay)
                        continue
                if response.ok:
                    data = response.json()
                    if data.get("code") == 20000:
                        token = data.get("token")
                        self.session.headers["Authorization"] = f"Bearer {token}"
                        self._save_cached_data()
                        self.logger.info(f"[{self.provider.name}] Login successful")
                        return {"message": "Login successful", "token": token}
                    self.logger.warning(f"[{self.provider.name}] Login failed: {response.text}")
                else:
                    self.logger.warning(f"[{self.provider.name}] Login failed: {response.text}")
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Login error: {e}")
            time.sleep(retry_delay)
        self.logger.error(f"[{self.provider.name}] Max login attempts reached")
        return {"message": "Login failed", "error": "Max attempts reached or Cloudflare block"}

    @BaseGameService.retry_on_failure()
    def add_user(self, username, password):
        payload = {"username": username, "password": password}
        response = self._make_request("POST", "/api/users", json=payload)
        data = response.json()
        return {"message": "User created", "username": username} if data.get("success") else {"message": "Failed to add user", "error": data.get("error")}

    @BaseGameService.retry_on_failure()
    def recharge(self, username, amount):
        user_id_response = self._search_user(username)
        if not user_id_response.get("user_id"):
            return {"message": "User not found", "error": user_id_response.get("error")}
        user_id = user_id_response["user_id"]
        agent_balance_response = self.get_agent_balance()
        if not agent_balance_response.get("balance"):
            return {"message": "Failed to get agent balance", "error": agent_balance_response.get("error")}
        payload = {
            "id": user_id,
            "available_balance": agent_balance_response["balance"],
            "opera_type": 0,
            "bonus": 0,
            "balance": amount,
            "remark": ""
        }
        response = self._make_request("POST", "/api/player/recharge", json=payload)
        data = response.json()
        return {"message": "Recharged successfully"} if data.get("message") == "Recharge successful" else {"message": "Failed to recharge", "error": data.get("message")}

    @BaseGameService.retry_on_failure()
    def redeem(self, username, amount):
        user_id_response = self._search_user(username)
        if not user_id_response.get("user_id"):
            return {"message": "User not found", "error": user_id_response.get("error")}
        user_id = user_id_response["user_id"]
        agent_balance_response = self.get_agent_balance()
        if not agent_balance_response.get("balance"):
            return {"message": "Failed to get agent balance", "error": agent_balance_response.get("error")}
        payload = {
            "id": user_id,
            "available_balance": agent_balance_response["balance"],
            "opera_type": 1,
            "bonus": 0,
            "balance": amount,
            "remark": ""
        }
        response = self._make_request("POST", "/api/player/redeem", json=payload)
        data = response.json()
        return {"message": "Redeemed successfully"} if data.get("message") == "Redeem successful" else {"message": "Failed to redeem", "error": data.get("message")}

    @BaseGameService.retry_on_failure()
    def reset_password(self, username, new_password):
        user_id_response = self._search_user(username)
        if not user_id_response.get("user_id"):
            return {"message": "User not found", "error": user_id_response.get("error")}
        user_id = user_id_response["user_id"]
        payload = {"id": user_id, "new_password": new_password, "confirm_password": new_password}
        response = self._make_request("POST", "/api/player/reset_password", json=payload)
        data = response.json()
        return {"message": "Password reset successful"} if data.get("message") == "Password reset successful" else {"message": "Failed to reset password", "error": data.get("message")}

    @BaseGameService.retry_on_failure()
    def get_balances(self, username):
        user_id_response = self._search_user(username)
        if not user_id_response.get("user_id"):
            return {"message": "User not found", "error": user_id_response.get("error")}
        user_id = user_id_response["user_id"]
        response = self._make_request("GET", f"/api/player/{user_id}/balance")
        data = response.json()
        return {"message": "Balance fetched", "balance": data["balance"]} if "balance" in data else {"message": "Failed to fetch balance", "error": "Balance not found"}

    @BaseGameService.retry_on_failure()
    def get_agent_balance(self):
        response = self._make_request("GET", "/api/agent/balance")
        data = response.json()
        return {"balance": data["balance"]} if "balance" in data else {"message": "Failed to get agent balance", "error": "Balance not found"}

    def _search_user(self, username):
        response = self._make_request("GET", f"/api/users/search?username={username}")
        data = response.json()
        return {"user_id": data["user_id"]} if data.get("user_id") else {"error": data.get("error", "User not found")}