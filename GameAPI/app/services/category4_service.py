"""
Service class for Category 4 game providers (e.g., Vblink).
Handles AES-encrypted payloads and signatures.
"""
# app/services/category4_service.py
import hashlib
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
from .base_service import BaseGameService
import uuid

class Category4Service(BaseGameService):
    """Service for Category 4 providers."""
    SECRET_KEY = "#s3LEA3RpR6PNmbWtuBCPn!4gS2DNM44"

    def _encrypt_data(self, data, timestamp):
        """Encrypt data using AES."""
        key = key = "1234567890abcdef".encode('utf-8')
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted = cipher.encrypt(pad(data.encode(), AES.block_size))
        return base64.b64encode(encrypted).decode()

    def _finalize_payload(self, data, timestamp):
        """Sign and finalize the payload."""
        data_string = "".join(str(data[k]) for k in sorted(data) if data[k])
        sign = hashlib.md5((data_string + str(timestamp) + self.SECRET_KEY).encode()).hexdigest()
        return {"sign": sign, "stime": timestamp, **data}

    @BaseGameService.retry_on_failure()
    def login(self, username, password, max_retries=3, retry_delay=2):
        for attempt in range(max_retries):
            try:
                # Generate a visitorId (UUID as a simple approximation)
                visitor_id = str(uuid.uuid4())
                payload = {
                    "LoginForm[login]": username,
                    "LoginForm[password]": password,
                    "visitorId": visitor_id,
                }
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://river-pay.com",
                    "Referer": "https://river-pay.com/office/login",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                }
                self.logger.info(f"[{self.provider.name}] Sending login payload: {payload}")
                response = self._make_request("POST", "/office/login", data=payload, headers=headers, timeout=20, allow_redirects=True)
                self.logger.debug(f"[{self.provider.name}] Login response: {response.status_code} - {response.text[:500]}")
                
                # Check for 302 redirect to index as success
                if response.status_code == 302 and "office/index" in response.headers.get("Location", ""):
                    # Store cookies for session
                    self.session.cookies.update(response.cookies)
                    self._save_cached_data()
                    self.logger.info(f"[{self.provider.name}] Login successful")
                    return {"message": "Login successful"}
                else:
                    self.logger.warning(f"[{self.provider.name}] Login failed: {response.text[:500]}")
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Login error: {e}")
            time.sleep(retry_delay)
        self.logger.error(f"[{self.provider.name}] Max login attempts reached")
        return {"message": "Login failed", "error": "Max attempts reached"}

    @BaseGameService.retry_on_failure()
    def add_user(self, username, password):
        """Add a new user with encrypted payload."""
        timestamp = int(time.time() * 1000)
        payload = self._finalize_payload({
            "token": self.session.headers.get("Authorization", "").split()[1] if "Authorization" in self.session.headers else "dummy-token",
            "account": username,
            "pwd": password,
        }, timestamp)
        response = self._make_request("POST", "/api/account/savePlayer", json=payload)
        if response.ok:
            data = response.json()
            if data.get("code") == 20000:
                self.logger.info(f"[{self.provider.name}] User {username} added successfully")
                return {"message": "User created", "username": username}
            return {"message": "Failed to add user", "error": data.get("message")}
        return {"message": "Failed to add user", "error": response.text}

    @BaseGameService.retry_on_failure()
    def recharge(self, username, amount):
        """Recharge a user's account."""
        timestamp = int(time.time() * 1000)
        payload = self._finalize_payload({
            "token": self.session.headers.get("Authorization", "").split()[1] if "Authorization" in self.session.headers else "dummy-token",
            "account": username,
            "score": amount,
            "user_type": "player",
        }, timestamp)
        response = self._make_request("POST", "/api/account/enterScore", json=payload)
        if response.ok:
            data = response.json()
            if data.get("code") == 20000:
                self.logger.info(f"[{self.provider.name}] Recharge successful for {username}")
                return {"message": "Recharged successfully"}
            return {"message": "Failed to recharge", "error": data.get("message")}
        return {"message": "Failed to recharge", "error": response.text}

    @BaseGameService.retry_on_failure()
    def redeem(self, username, amount):
        """Redeem funds from a user's account."""
        timestamp = int(time.time() * 1000)
        payload = self._finalize_payload({
            "token": self.session.headers.get("Authorization", "").split()[1] if "Authorization" in self.session.headers else "dummy-token",
            "account": username,
            "score": -amount,  # Negative for redeem
            "user_type": "player",
        }, timestamp)
        response = self._make_request("POST", "/api/account/enterScore", json=payload)
        if response.ok:
            data = response.json()
            if data.get("code") == 20000:
                self.logger.info(f"[{self.provider.name}] Redeem successful for {username}")
                return {"message": "Redeemed successfully"}
            return {"message": "Failed to redeem", "error": data.get("message")}
        return {"message": "Failed to redeem", "error": response.text}

    @BaseGameService.retry_on_failure()
    def change_password(self, username, new_password):
        """Change a user's password."""
        timestamp = int(time.time() * 1000)
        payload = self._finalize_payload({
            "token": self.session.headers.get("Authorization", "").split()[1] if "Authorization" in self.session.headers else "dummy-token",
            "account": username,
            "pwd": new_password,
            "name": "",
            "tel_area_code": "",
            "phone": "",
            "remark": "",
        }, timestamp)
        response = self._make_request("POST", "/api/account/updatePlayer", json=payload)
        if response.ok:
            data = response.json()
            if data.get("code") == 20000:
                self.logger.info(f"[{self.provider.name}] Password changed for {username}")
                return {"message": "Password changed successfully"}
            return {"message": "Failed to change password", "error": data.get("message")}
        return {"message": "Failed to change password", "error": response.text}

    @BaseGameService.retry_on_failure()
    def get_balances(self, username):
        """Fetch user balance."""
        timestamp = int(time.time() * 1000)
        payload = self._finalize_payload({
            "token": self.session.headers.get("Authorization", "").split()[1] if "Authorization" in self.session.headers else "dummy-token",
            "account": username,
            "type": 2,
        }, timestamp)
        response = self._make_request("POST", "/api/search/Account", json=payload)
        if response.ok:
            data = response.json()
            if data.get("code") == 20000 and data["list"]:
                user_data = data["list"][1]
                self.logger.info(f"[{self.provider.name}] Balance fetched for {username}")
                return {"message": "Balance fetched", "balance": user_data.get("Score")}
            return {"message": "Failed to fetch balance", "error": data.get("message")}
        return {"message": "Failed to fetch balance", "error": response.text}

    @BaseGameService.retry_on_failure()
    def get_agent_balance(self):
        """Fetch agent's balance."""
        timestamp = int(time.time() * 1000)
        payload = self._finalize_payload({
            "token": self.session.headers.get("Authorization", "").split()[1] if "Authorization" in self.session.headers else "dummy-token",
        }, timestamp)
        response = self._make_request("POST", "/api/user/CurScore", json=payload)
        if response.ok:
            data = response.json()
            if data.get("code") == 20000:
                self.logger.info(f"[{self.provider.name}] Agent balance fetched")
                return {"message": "Agent balance fetched", "balance": data.get("LimitNum")}
            return {"message": "Failed to fetch agent balance", "error": data.get("message")}
        return {"message": "Failed to fetch agent balance", "error": response.text}

    def _search_user(self, username):
        response = self._make_request("GET", f"/api/users/search?username={username}")
        data = response.json()
        return {"user_id": data["user_id"]} if data.get("user_id") else {"error": data.get("error", "User not found")}