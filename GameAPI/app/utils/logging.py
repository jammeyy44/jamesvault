"""
Utility for logging API requests.
"""

from app.models import APILog
from app import db
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )


def log_api_call(account_id, token, remote_provider, method, path, status_code, is_successful, description=None):
    """Log an API request."""
    log = APILog(
        account_id=account_id,
        token=token,
        remote_provider=remote_provider,
        method=method,
        path=path,
        status_code=status_code,
        is_successful=is_successful,
        description=description
    )
    db.session.add(log)
    db.session.commit()