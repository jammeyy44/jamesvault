"""
Service class for Category 3 game providers (e.g., Orion Stars).
Handles web page interactions and form submissions.
"""
import time
from bs4 import BeautifulSoup
import re
from .base_service import BaseGameService

class Category3Service(BaseGameService):
    """Service for Category 3 providers."""

    ACTION_URL_PATTERNS = {
        "recharge": r"Module/AccountManager/GrantTreasure\.aspx\?param=[A-Za-z0-9]+",
        "redeem": r"Module/AccountManager/ChangeTreasure\.aspx\?param=[A-Za-z0-9]+",
        "password": r"Module/AccountManager/ResetPassWord\.aspx\?param=[A-Za-z0-9]+",
    }

    def _extract_hidden_fields(self, response):
        """Extract __VIEWSTATE and __EVENTVALIDATION from HTML."""
        soup = BeautifulSoup(response.text, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value'] if soup.find('input', {'name': '__VIEWSTATE'}) else ''
        eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})['value'] if soup.find('input', {'name': '__EVENTVALIDATION'}) else ''
        viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value'] if soup.find('input', {'name': '__VIEWSTATEGENERATOR'}) else ''
        self.logger.debug(f"[{self.provider.name}] VIEWSTATE: {viewstate[:50]}, EVENTVALIDATION: {eventvalidation[:50]}, VIEWSTATEGENERATOR: {viewstategenerator}")
        return viewstate, eventvalidation, viewstategenerator

    def _solve_captcha(self):
        """Solve CAPTCHA using 2Captcha."""
        captcha_url = f"{self.base_url}/Tools/VerifyImagePage.aspx?{int(time.time())}"
        self.logger.info(f"[{self.provider.name}] Fetching CAPTCHA from: {captcha_url}")
        try:
            code = self.solve_image_captcha(captcha_url)
            self.logger.info(f"[{self.provider.name}] CAPTCHA solved")
            return code
        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"[{self.provider.name}] CAPTCHA solving failed: {e}")
            return None

    def _extract_dynamic_url(self, response, action):
        """Extract action-specific URL."""
        pattern = self.ACTION_URL_PATTERNS.get(action)
        match = re.search(pattern, response.text)
        if match:
            full_url = f"{self.base_url}/{match.group(0)}"
            self.logger.info(f"[{self.provider.name}] Extracted {action} URL: {full_url}")
            return full_url
        self.logger.error(f"[{self.provider.name}] Failed to extract URL for {action}")
        return None

    def _submit_form(self, url, payload):
        """Submit a form and return the response message."""
        response = self._make_request("POST", url, data=payload)
        if response.ok:
            pattern = r'Alter\("([^"]+)"'
            match = re.search(pattern, response.text)
            message = match.group(1) if match else "Failed to parse response message"
            self.logger.info(f"[{self.provider.name}] Form submission response: {message}")
            return message
        error_msg = f"Server unreachable: {response.status_code}"
        self.logger.error(f"[{self.provider.name}] {error_msg}")
        return error_msg

    def login(self, username, password, max_retries=3, retry_delay=2):
        """Log in by submitting the login form (the image CAPTCHA needs CAPTCHA_API_KEY)."""
        for attempt in range(max_retries):
            try:
                self.logger.info(f"[{self.provider.name}] Login attempt {attempt + 1}/{max_retries}")
                response = self._make_request("GET", "/default.aspx", timeout=20)
                viewstate, eventvalidation, viewstategenerator = self._extract_hidden_fields(response)
                if not viewstate or not eventvalidation:
                    self.logger.error(f"[{self.provider.name}] Missing hidden fields")
                    continue

                captcha_code = self._solve_captcha()
                if not captcha_code:
                    continue

                payload = {
                    "__VIEWSTATE": viewstate,
                    "__EVENTVALIDATION": eventvalidation,
                    "__VIEWSTATEGENERATOR": viewstategenerator,
                    "txtLoginName": username,
                    "txtLoginPass": password,
                    "txtVerifyCode": captcha_code,
                    "btnLogin": "Login in",
                }
                self.logger.info(f"[{self.provider.name}] Submitting login payload: {payload}")
                response = self._make_request("POST", "/default.aspx", data=payload, timeout=20)
                self.logger.debug(f"[{self.provider.name}] Login response: {response.text[:500]}")
                success_indicators = ["Welcome", "Dashboard", "Account", "Logged in", "User Management", "AccountsList"]
                if any(indicator.lower() in response.text.lower() for indicator in success_indicators):
                    self._save_cached_data()
                    self.logger.info(f"[{self.provider.name}] Login successful, session cookies set")
                    # Optionally return cookies for debugging
                    cookies = self.session.cookies.get_dict()
                    self.logger.info(f"[{self.provider.name}] Session cookies: {cookies}")
                    return {"message": "Login successful"}
                self.logger.warning(f"[{self.provider.name}] Login failed, no success indicators found")
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Login error: {e}")
            time.sleep(retry_delay)
        self.logger.error(f"[{self.provider.name}] Max login attempts reached")
        return {"message": "Login failed", "error": "Max attempts reached"}

    def add_user(self, username, password, max_retries=3, retry_delay=2):
        """Add a new user by submitting the form."""
        url = "/Module/AccountManager/CreateAccount.aspx"
        for attempt in range(max_retries):
            try:
                self.logger.info(f"[{self.provider.name}] Add user attempt {attempt + 1}/{max_retries}")
                # Fetch the form page to get hidden fields
                response = self.session.get(f"{self.base_url}{url}")
                self.logger.debug(f"[{self.provider.name}] GET {url} response: {response.text[:500]}")
                if "txtLoginName" in response.text:  # Check if redirected to login
                    self.logger.error(f"[{self.provider.name}] Session expired, re-authenticating")
                    login_result = self.login(self.provider.username, self.provider.password)
                    if login_result["message"] != "Login successful":
                        return {"message": "Failed to add user", "error": "Re-authentication failed"}
                    response = self.session.get(f"{self.base_url}{url}")
                    self.logger.debug(f"[{self.provider.name}] GET {url} after re-auth: {response.text[:500]}")

                viewstate, eventvalidation, viewstategenerator = self._extract_hidden_fields(response)
                if not viewstate or not eventvalidation:
                    self.logger.error(f"[{self.provider.name}] Missing hidden fields")
                    time.sleep(retry_delay)
                    continue

                payload = {
                    "__EVENTTARGET": "ctl07",
                    "__VIEWSTATE": viewstate,
                    "__EVENTVALIDATION": eventvalidation,
                    "__VIEWSTATEGENERATOR": viewstategenerator,
                    "txtAccount": username,
                    "txtNickName": username,  # Optional, defaults to username
                    "txtLogonPass": password,
                    "txtLogonPass2": password,
                }
                self.logger.info(f"[{self.provider.name}] Sending payload: {payload}")
                response = self.session.post(f"{self.base_url}{url}", data=payload)
                self.logger.debug(f"[{self.provider.name}] POST {url} response: {response.text[:500]}")
                match = re.search(r'Alter\("([^"]+)"', response.text)
                if match:
                    message = match.group(1)
                    if message == "Added successfully":
                        self.logger.info(f"[{self.provider.name}] User {username} added successfully")
                        return {"message": "User created", "username": username}
                    return {"message": "Failed to add user", "error": message}
                return {"message": "Failed to add user", "error": "Failed to parse response message"}
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Add user error: {str(e)}")
                time.sleep(retry_delay)
        return {"message": "Failed to add user", "error": "Max retries reached"}

    def recharge(self, username, amount):
        user_id, game_id = self._search_user(username)
        if not user_id or not game_id:
            return {"message": "User not found", "error": "Search failed"}
        payload = {"tourl": "0", "getpassuid": user_id, "getpassgid": game_id}
        response = self._make_request("POST", "/Module/AccountManager/AccountsList.aspx", data=payload)
        if response.ok:
            recharge_url = self._extract_dynamic_url(response, "recharge")
            if not recharge_url:
                return {"message": "Failed to recharge", "error": "Recharge URL not found"}
            recharge_page = self._make_request("GET", recharge_url.split(self.base_url)[1])
            if recharge_page.ok:
                viewstate, eventvalidation, _ = self._extract_hidden_fields(recharge_page)
                if not viewstate or not eventvalidation:
                    return {"message": "Failed to recharge", "error": "Missing hidden fields"}
                recharge_payload = {
                    "__EVENTTARGET": "Button1",
                    "__VIEWSTATE": viewstate,
                    "__EVENTVALIDATION": eventvalidation,
                    "txtAddGold": amount,
                }
                message = self._submit_form(recharge_url.split(self.base_url)[1], recharge_payload)
                if message == "Confirmed successful":
                    self.logger.info(f"[{self.provider.name}] Recharge successful for {username}")
                    return {"message": "Recharged successfully"}
                return {"message": "Failed to recharge", "error": message}
        return {"message": "Failed to recharge", "error": "Server unreachable"}

    def redeem(self, username, amount):
        user_id, game_id = self._search_user(username)
        if not user_id or not game_id:
            return {"message": "User not found", "error": "Search failed"}
        payload = {"tourl": "1", "getpassuid": user_id, "getpassgid": game_id}
        response = self._make_request("POST", "/Module/AccountManager/AccountsList.aspx", data=payload)
        if response.ok:
            redeem_url = self._extract_dynamic_url(response, "redeem")
            if not redeem_url:
                return {"message": "Failed to redeem", "error": "Redeem URL not found"}
            redeem_page = self._make_request("GET", redeem_url.split(self.base_url)[1])
            if redeem_page.ok:
                viewstate, eventvalidation, _ = self._extract_hidden_fields(redeem_page)
                if not viewstate or not eventvalidation:
                    return {"message": "Failed to redeem", "error": "Missing hidden fields"}
                redeem_payload = {
                    "__EVENTTARGET": "Button1",
                    "__VIEWSTATE": viewstate,
                    "__EVENTVALIDATION": eventvalidation,
                    "txtAddGold": amount,
                }
                message = self._submit_form(redeem_url.split(self.base_url)[1], redeem_payload)
                if message == "Confirmed successful":
                    self.logger.info(f"[{self.provider.name}] Redeem successful for {username}")
                    return {"message": "Redeemed successfully"}
                return {"message": "Failed to redeem", "error": message}
        return {"message": "Failed to redeem", "error": "Server unreachable"}

    def change_password(self, username, new_password):
        user_id, game_id = self._search_user(username)
        if not user_id or not game_id:
            return {"message": "User not found", "error": "Search failed"}
        payload = {"tourl": "2", "getpassuid": user_id, "getpassgid": game_id}
        response = self._make_request("POST", "/Module/AccountManager/AccountsList.aspx", data=payload)
        if response.ok:
            password_url = self._extract_dynamic_url(response, "password")
            if not password_url:
                return {"message": "Failed to change password", "error": "Password URL not found"}
            password_page = self._make_request("GET", password_url.split(self.base_url)[1])
            if password_page.ok:
                viewstate, eventvalidation, _ = self._extract_hidden_fields(password_page)
                if not viewstate or not eventvalidation:
                    return {"message": "Failed to change password", "error": "Missing hidden fields"}
                password_payload = {
                    "__EVENTTARGET": "Button1",
                    "__VIEWSTATE": viewstate,
                    "__EVENTVALIDATION": eventvalidation,
                    "txtConfirmPass": new_password,
                    "txtSureConfirmPass": new_password,
                }
                message = self._submit_form(password_url.split(self.base_url)[1], password_payload)
                if message == "Modified success!":
                    self.logger.info(f"[{self.provider.name}] Password changed for {username}")
                    return {"message": "Password changed successfully"}
                return {"message": "Failed to change password", "error": message}
        return {"message": "Failed to change password", "error": "Server unreachable"}

    def get_balances(self, username):
        user_id, game_id = self._search_user(username)
        if not user_id or not game_id:
            return {"message": "User not found", "error": "Search failed"}
        payload = {"getscoreuserid": user_id}
        response = self._make_request("POST", "/Module/AccountManager/AccountsList.aspx", data=payload)
        if response.ok:
            pattern = r"(\d+\.?\d*)@"
            match = re.search(pattern, response.text)
            if match:
                self.logger.info(f"[{self.provider.name}] Balance fetched for {username}: {match.group(1)}")
                return {"message": "Balance fetched", "balance": match.group(1)}
            return {"message": "Failed to fetch balance", "error": "Balance not found"}
        return {"message": "Failed to fetch balance", "error": "Server unreachable"}

    def get_agent_balance(self):
        response = self._make_request("GET", "/Module/AccountManager/AccountsList.aspx")
        if response.ok:
            pattern = r'updateBalance\("Balance:(\d+\.?\d*)"\)'
            match = re.search(pattern, response.text)
            if match:
                self.logger.info(f"[{self.provider.name}] Agent balance fetched: {match.group(1)}")
                return {"message": "Agent balance fetched", "balance": match.group(1)}
            return {"message": "Failed to fetch agent balance", "error": "Balance not found"}
        return {"message": "Failed to fetch agent balance", "error": "Server unreachable"}

    def _search_user(self, username, max_retries=3, retry_delay=2):
        """Search for a user by username."""
        for attempt in range(max_retries):
            try:
                payload = {"__EVENTTARGET": "ctl16", "txtSearch": username}
                response = self._make_request("POST", "/Module/AccountManager/AccountsList.aspx", data=payload)
                self.logger.debug(f"[{self.provider.name}] Search response: {response.text[:500]}")
                pattern = r"updateSelect\(\s*'(\d+),(\d+)'\s*\)"
                match = re.search(pattern, response.text)
                if match:
                    user_id, game_id = match.groups()
                    self.logger.info(f"[{self.provider.name}] User {username} found - UserID: {user_id}, GameID: {game_id}")
                    return user_id, game_id
                self.logger.warning(f"[{self.provider.name}] User {username} not found in response")
                return None, None
            except Exception as e:
                self.logger.error(f"[{self.provider.name}] Search error: {str(e)}")
                time.sleep(retry_delay)
        self.logger.error(f"[{self.provider.name}] Max search attempts reached for {username}")
        return None, None
