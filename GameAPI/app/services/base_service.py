"""
Base service class for all game providers.
Handles common functionality like session management, caching, and error handling.
"""
# app/services/base_service.py
import base64
import time
import requests
from functools import wraps
from flask import current_app
from app import cache
import logging

logger = logging.getLogger("automater")

CAPTCHA_PLACEHOLDERS = {"", "your_actual_2captcha_api_key", "your-2captcha-api-key-here", "your_2captcha_api_key"}


class CaptchaError(Exception):
    """A CAPTCHA could not be fetched or solved. The message is for admins (provider log / connection test)."""

class BaseGameService:
    """Base class for game provider services."""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.5",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, provider):
        """Initialize with a provider object."""
        self.provider = provider
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        try:
            self._load_cached_data()
        except Exception as e:
            logger.error(f"Failed to load cached data for {self.provider.name}: {e}")
        self.logger = logger  # Logger is set here

    @property
    def base_url(self):
        """Return the provider's base URL."""
        return self.provider.base_url

    def _load_cached_data(self):
        """Load cached headers and cookies."""
        try:
            cached_headers = cache.get(f"{self.provider.name}_headers")
            if cached_headers:
                self.session.headers.update(cached_headers)
            cached_cookies = cache.get(f"{self.provider.name}_cookies")
            if cached_cookies:
                for k, v in cached_cookies.items():
                    self.session.cookies.set(k, v)
        except Exception as e:
            logger.error(f"Cache load error: {e}")

    def _save_cached_data(self):
        """Save headers and cookies to cache."""
        try:
            cache.set(f"{self.provider.name}_headers", dict(self.session.headers), timeout=None)
            cache.set(f"{self.provider.name}_cookies", requests.utils.dict_from_cookiejar(self.session.cookies), timeout=None)
        except Exception as e:
            logger.error(f"Cache save error: {e}")

    def _make_request(self, method, url, **kwargs):
        full_url = f"{self.provider.base_url}{url}"
        response = self.session.request(method, full_url, **kwargs)
        if response.status_code == 401 or "Login" in response.text and "overtime" in response.text:
            self.logger.info(f"[{self.provider.name}] Session expired, re-authenticating")
            login_result = self.login(self.provider.username, self.provider.password)
            if login_result.get("message") != "Login successful":
                raise ValueError("Re-authentication failed")
            response = self.session.request(method, full_url, **kwargs)
        response.raise_for_status()
        return response

    def solve_image_captcha(self, url):
        """Solve an image CAPTCHA with 2Captcha.

        The image is fetched with THIS session (same cookies and browser headers the login will use, so the code matches the
        session) and sent to 2Captcha as base64. Passing the URL instead makes 2Captcha's client download it anonymously, which
        providers refuse. The key comes from configuration only."""
        api_key = (current_app.config.get("CAPTCHA_API_KEY") or "").strip()
        if api_key in CAPTCHA_PLACEHOLDERS:
            raise CaptchaError("CAPTCHA_API_KEY is not set (add your 2Captcha key to the server environment)")
        try:
            resp = self.session.get(url, timeout=15)
        except requests.RequestException as e:
            raise CaptchaError(f"could not fetch the CAPTCHA image ({type(e).__name__})") from e
        if resp.status_code != 200 or not resp.content:
            raise CaptchaError(f"could not fetch the CAPTCHA image (HTTP {resp.status_code})")
        from twocaptcha import TwoCaptcha
        try:
            result = TwoCaptcha(api_key).normal(base64.b64encode(resp.content).decode())
        except Exception as e:  # 2Captcha errors: bad key, no balance, unsolvable image...
            raise CaptchaError(f"2Captcha could not solve it: {e}") from e
        return result["code"]

    def _search_user(self, username):
        # Placeholder, to be overridden by subclasses if needed
        return {"user_id": None, "error": "Not implemented"}

    def login(self):
        """Abstract login method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement login method")

    def retry_on_failure(max_retries=3, base_delay=2):
        """Retry Wrapper for Session handling"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                attempts = 0
                while attempts < max_retries:
                    try:
                        return func(*args, **kwargs)
                    except (requests.RequestException, ValueError) as e:
                        attempts += 1
                        if attempts == max_retries:
                            raise e from None
                        delay = base_delay * (2 ** attempts)
                        time.sleep(delay)
                        args[0].logger.warning(f"Retry {attempts}/{max_retries} for {func.__name__} after {delay}s")
            return wrapper
        return decorator
