"""
Configuration settings for the application.
"""

import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

def _flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


JV_ENV = os.getenv("JV_ENV", "development")
_DEFAULT_SECRET = "mysecretkey"

if JV_ENV == "production" and os.getenv("SECRET_KEY", _DEFAULT_SECRET) == _DEFAULT_SECRET:
    raise RuntimeError("SECRET_KEY must be set to a strong random value when JV_ENV=production")


if JV_ENV == "production" and _flag("JV_SANDBOX", False):
    raise RuntimeError("JV_SANDBOX must not be enabled when JV_ENV=production")
if JV_ENV == "production" and not _flag("JV_RATE_LIMITS", True):
    raise RuntimeError("JV_RATE_LIMITS must not be disabled when JV_ENV=production")


class Config:
    """Configuration class for Flask app."""
    SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
    JV_ENV = JV_ENV
    # Uploaded game thumbnails live here (use a persistent volume in production). Requests are capped to keep uploads small.
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    # Only ever turned off for automated browser tests (refused in production).
    RATE_LIMITS_ENABLED = _flag("JV_RATE_LIMITS", True)

    # Session cookies (player + admin). Set JV_COOKIE_SECURE=true behind HTTPS.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _flag("JV_COOKIE_SECURE", JV_ENV == "production")
    PERMANENT_SESSION_LIFETIME = int(os.getenv("JV_SESSION_SECONDS", 60 * 60 * 24 * 7))

    # Brand (central place to rename / re-skin; the frontend reads these via /api/v1/site/config)
    BRAND = {
        "name": os.getenv("BRAND_NAME", "stakesweep.net"),
        "tagline": os.getenv("BRAND_TAGLINE", "Your next winning moment starts here."),
        "support_email": os.getenv("BRAND_SUPPORT_EMAIL", ""),
        "min_age": int(os.getenv("BRAND_MIN_AGE", 18)),
    }

    # Feature flags. Money movement stays OFF until licensing, jurisdiction and payment provider are verified.
    FEATURES = {
        "wallet": _flag("JV_ENABLE_WALLET", False),
        "game_launch": _flag("JV_ENABLE_GAME_LAUNCH", False),
        "reward_wheel": _flag("JV_ENABLE_WHEEL", True),
        "registration": _flag("JV_ENABLE_REGISTRATION", True),
        # Create provider game accounts for players (uses the unverified live adapters).
        "game_accounts": _flag("JV_ENABLE_GAME_ACCOUNTS", False),
        # Accept "Add Cash" requests in live mode (staff confirm payment, then recharge runs once).
        "cash_requests": _flag("JV_ENABLE_CASH_REQUESTS", False),
        # Development only: fake accounts/balances stored locally, flagged in the UI. Refused in production.
        "sandbox": _flag("JV_SANDBOX", False),
    }
    # Payment provider (Paydora). Secrets come from the environment only.
    PAYDORA_BASE_URL = os.getenv("PAYDORA_BASE_URL", "https://cpcs.paydora.net/api/v1")
    PAYDORA_API_KEY = os.getenv("PAYDORA_API_KEY", "")
    PAYDORA_WEBHOOK_SECRET = os.getenv("PAYDORA_WEBHOOK_SECRET", "")
    # Number of reverse proxies in front of Flask that append to X-Forwarded-For (0 = use the socket address).
    TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", 0))
    SANDBOX_WELCOME_DIAMONDS = 30  # test diamonds for new accounts, ONLY when JV_SANDBOX is on (never in production)
    DEPOSIT_TASK_MIN = int(os.getenv("DEPOSIT_TASK_MIN", 20))  # dollars, for the daily-deposit Bonus Zone task
    # Bounds for deposit methods that accept any amount (methods with fixed amount lists use those lists).
    DEPOSIT_MIN = Decimal(os.getenv("DEPOSIT_MIN", "5"))  # the cashout table starts at a $5 deposit
    DEPOSIT_MAX = Decimal(os.getenv("DEPOSIT_MAX", "1000"))
    CASHOUT_MIN = Decimal(os.getenv("CASHOUT_MIN", "50"))  # minimum wallet withdrawal: a $50 balance can withdraw
    CASHOUT_MAX = Decimal(os.getenv("CASHOUT_MAX", "500"))
    CASH_MIN = Decimal(os.getenv("CASH_MIN", "5"))
    CASH_MAX = Decimal(os.getenv("CASH_MAX", "500"))
    CASH_QUICK = [5, 10, 25]
    PROVIDER_ACCOUNT_KEY = os.getenv("PROVIDER_ACCOUNT_KEY", "")

    # Emails reserved for superadmin accounts. Used ONLY by `python seed_site.py` to pre-create the accounts;
    # registration never grants a role, so nobody can claim these addresses by signing up.
    ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "jammeyy44@gmail.com").split(",") if e.strip()]

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    CORS_ORIGINS = [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o]
    PASSWORD_RESET_MINUTES = int(os.getenv("PASSWORD_RESET_MINUTES", 30))

    # Outbound email (password reset). Without SMTP_HOST nothing is sent; in development the link is logged.
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@localhost")
    # Example: SQLALCHEMY_DATABASE_URI = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST', '127.0.0.1')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://username:password@127.0.0.1:5432/gameapis"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Hosted PostgreSQL (e.g. Supabase's pooler) closes idle connections and limits clients: check a connection before
    # using it, recycle before the server drops it, fail fast on connect, and keep the pool small.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"pool_pre_ping": True, "pool_recycle": 240, "pool_size": 5, "max_overflow": 5, "connect_args": {"connect_timeout": 10}}
        if os.getenv("DATABASE_URL", "").startswith(("postgresql", "postgres:"))
        else {"pool_pre_ping": True}
    )

    # Caching mechanism
    # Caching configuration with Redis
    CACHE_TYPE = 'redis'
    CACHE_REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    CACHE_REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    CACHE_REDIS_DB = int(os.getenv('REDIS_DB', 0))
    CACHE_REDIS_URL = os.getenv('CACHE_REDIS_URL', f'redis://{os.getenv("REDIS_HOST", "localhost")}:{os.getenv("REDIS_PORT", "6379")}/{os.getenv("REDIS_DB", "0")}')
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300))  # 5 minutes default

    # TwoCaptcha Settings
    CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "your-2captcha-api-key-here")

   # Provider URLs for each category (list all providers)
    CATEGORY1_PROVIDERS = [
        "https://agentserver.gameroom777.com",
        "http://agentserver.cashmachine777.com:8003",
        "https://agentserver.mrallinone777.com",
        "http://agentserver.mafia77777.com:8003",
        "http://agentserver.cashfrenzy777.com:8003",
        "http://agentserver.slots88888.com:8003"
    ]
    CATEGORY2_PROVIDERS = [
        "https://agent.gamevault999.com",
        "https://agent.lasvegassweeps.com",
        "https://ht.juwa777.com"
    ]
    CATEGORY3_PROVIDERS = [
        "https://firekirin.xyz:8888",
        "https://www.pandamaster.vip",
        "https://milkywayapp.xyz:8781",
        "https://orionstars.vip:8781"
    ]
    CATEGORY4_PROVIDERS = [
        "https://gm.vblink777.club",
        "https://ht.ultrapanda.mobi",
        "https://pko.egame99.club"
    ]
    # Gamebase provider (if needed)
    GAMEBASE_URL = "https://river-pay.com"
