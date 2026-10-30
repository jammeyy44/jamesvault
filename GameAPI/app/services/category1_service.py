"""
Service class for Category 1 game providers (e.g., Gameroom).
Handles token-based authentication and operations.
"""

import time
from flask import current_app
from .base_service import BaseGameService
import requests
from bs4 import BeautifulSoup

class Category1Service(BaseGameService):
    """Service for Category 1 providers."""
    def __init__(self, provider):
        self.provider = provider
        self.session = requests.Session()
        self.logger = current_app.logger
        self._load_cached_token()

    def _load_cached_token(self):
        cached_token = current_app.config.get(f"TOKEN_{self.provider.id}")
        if cached_token:
            self.session.headers["Authorization"] = f"Bearer {cached_token}"

    def _save_cached_token(self, token):
        current_app.config[f"TOKEN_{self.provider.id}"] = token

    
    @BaseGameService.retry_on_failure()
    def login(self, username, password, max_retries=3, retry_delay=3):
        for attempt in range(max_retries):
            try:
                payload = {"username": username, "password": password}
                response = self._make_request("POST", "/api/login", json=payload)  # Use JSON for consistency
                data = response.json()
                self.logger.info(f"Login response: {data}")
                if data.get("message") == "Users login succeeded":
                    token = data.get("token")
                    self.session.headers["Authorization"] = f"Bearer {token}"
                    self._save_cached_data()
                    self._save_cached_token(token)
                    self.logger.info(f"[{self.provider.name}] Login successful")
                    return {"message": "Login successful", "token": token}
                else:
                    self.logger.warning(f"[{self.provider.name}] Login failed: {data}")
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Login error: {e}")
            time.sleep(retry_delay)
        self.logger.error(f"[{self.provider.name}] Max login attempts reached")
        return {"message": "Login failed", "error": "Max attempts reached"}

    @BaseGameService.retry_on_failure()
    def get_balances(self, username, max_retries=3, retry_delay=2):
        user_response = self._search_user(username, max_retries, retry_delay)
        if not user_response["user_id"]:
            return {"message": "User not found", "error": user_response["error"]}
        return {"message": "Balance fetched", "balance": str(user_response["balance"])}

    @BaseGameService.retry_on_failure()
    def add_user(self, username, password, max_retries=3, retry_delay=2):
        payload = {
            "username": username,
            "password": password,
            "password_confirmation": password,
        }
        for attempt in range(max_retries):
            try:
                response = self._make_request("POST", "/api/player/playerInsert", json=payload)
                data = response.json()
                self.logger.info(f"Add user response: {data}")
                if data.get("message") == "Insert successful":
                    self.logger.info(f"[{self.provider.name}] User {username} created")
                    return {"message": "User created", "user_id": data.get("user_id"), "username": username}
                return {"message": "Failed to add user", "error": data.get("message")}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Add user error: {str(e)}")
                time.sleep(retry_delay)
        return {"message": "Failed to add user", "error": "Max retries reached"}

    @BaseGameService.retry_on_failure()
    def _search_user(self, username, max_retries=3, retry_delay=2):
        for attempt in range(max_retries):
            try:
                params = {"account": username}
                response = self._make_request("GET", "/api/player/userList", params=params)
                data = response.json()
                self.logger.info(f"Search response: {data}")
                if data.get("message") == "Query successful" and data.get("data"):
                    user = data["data"][0]
                    self.logger.info(f"[{self.provider.name}] User {username} found, ID: {user['Id']}")
                    return {"user_id": user["Id"], "balance": user.get("score", "0"), "error": None}
                return {"user_id": None, "balance": None, "error": "User not found"}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Search error: {str(e)}")
                time.sleep(retry_delay)
        return {"user_id": None, "balance": None, "error": "Max retries reached"}

    @BaseGameService.retry_on_failure()
    def get_agent_balance(self, max_retries=3, retry_delay=2):
        for attempt in range(max_retries):
            try:
                # Scrape /admin first
                response = self._make_request("GET", "/admin")
                soup = BeautifulSoup(response.text, "html.parser")
                balance_element = soup.find("span", id="money")
                self.logger.info(f"[{self.provider.name}] /admin snippet: {response.text[:500]}")
                if balance_element:
                    balance = balance_element.text.strip()
                    self.logger.info(f"[{self.provider.name}] Agent balance scraped: {balance}")
                    if balance and balance != "0":  # Avoid initial 0
                        return {"message": "Agent balance fetched", "balance": balance}
                
                # Fallback to API
                response = self._make_request("GET", "/api/agent/getMoney")
                data = response.json()
                self.logger.info(f"[{self.provider.name}] API response: {data}")
                balance = data.get("money", None)
                if balance is not None:
                    self.logger.info(f"[{self.provider.name}] Agent balance via API: {balance}")
                    return {"message": "Agent balance fetched", "balance": str(balance)}
                return {"message": "Balance not found", "error": "No balance in response"}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Error fetching agent balance: {str(e)}")
                time.sleep(retry_delay)
        return {"message": "Failed to fetch agent balance", "error": "Max retries reached"}

    @BaseGameService.retry_on_failure()
    def recharge(self, username, amount, max_retries=3, retry_delay=2):
        user_response = self._search_user(username)
        if not user_response["user_id"]:
            return {"message": "User not found", "error": user_response["error"]}
        
        user_id = user_response["user_id"]
        agent_balance_response = self.get_agent_balance()
        if "error" in agent_balance_response:
            return {"message": "Failed to get agent balance", "error": agent_balance_response["error"]}

        payload = {
            "id": user_id,
            "available_balance": agent_balance_response["balance"],
            "opera_type": 0,  # Recharge
            "bonus": 0,
            "balance": amount,
            "remark": ""
        }
        for attempt in range(max_retries):
            try:
                response = self._make_request("POST", "/api/player/agentRecharge", json=payload)
                data = response.json()
                self.logger.info(f"Recharge response: {data}")
                if data.get("message") == "Recharge successful":
                    self.logger.info(f"[{self.provider.name}] Recharge successful for {username}")
                    return {"message": "Recharged successfully"}
                return {"message": "Failed to recharge", "error": data.get("message")}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Recharge error: {str(e)}")
                time.sleep(retry_delay)
        return {"message": "Failed to recharge", "error": "Max retries reached"}

    @BaseGameService.retry_on_failure()
    def redeem(self, username, amount, max_retries=3, retry_delay=2):
        user_response = self._search_user(username)
        if not user_response["user_id"]:
            return {"message": "User not found", "error": user_response["error"]}
        
        user_id = user_response["user_id"]
        agent_balance_response = self.get_agent_balance()
        if "error" in agent_balance_response:
            return {"message": "Failed to get agent balance", "error": agent_balance_response["error"]}

        payload = {
            "id": user_id,
            "customer_balance": agent_balance_response["balance"],
            "opera_type": 1,  # Withdraw
            "balance": amount,
            "remark": ""
        }
        for attempt in range(max_retries):
            try:
                response = self._make_request("POST", "/api/player/agentWithdraw", json=payload)
                data = response.json()
                self.logger.info(f"Redeem response: {data}")
                if data.get("message") == "Withdraw successful":
                    self.logger.info(f"[{self.provider.name}] Redeem successful for {username}")
                    return {"message": "Redeemed successfully"}
                return {"message": "Failed to redeem", "error": data.get("message")}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Redeem error: {str(e)}")
                time.sleep(retry_delay)
        return {"message": "Failed to redeem", "error": "Max retries reached"}

    @BaseGameService.retry_on_failure()
    def change_password(self, username, new_password, max_retries=3, retry_delay=2):
        user_response = self._search_user(username)
        if not user_response["user_id"]:
            return {"message": "User not found", "error": user_response["error"]}
        
        user_id = user_response["user_id"]
        payload = {
            "id": user_id,
            "password": new_password,
            "password_confirmation": new_password
        }
        for attempt in range(max_retries):
            try:
                response = self._make_request("POST", "/admin/player/resetpw", json=payload)
                data = response.json()
                self.logger.info(f"Reset password response: {data}")
                if data.get("message") == "Reset successful":
                    self.logger.info(f"[{self.provider.name}] Password reset for {username}")
                    return {"message": "Password changed successfully"}
                return {"message": "Failed to change password", "error": data.get("message")}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Password reset error: {str(e)}")
                time.sleep(retry_delay)
        return {"message": "Failed to change password", "error": "Max retries reached"}