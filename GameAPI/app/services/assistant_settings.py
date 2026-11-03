"""Settings for the voice assistant's AI provider: an admin pastes the API key in the admin panel instead of editing .env.

The key is stored encrypted (AES-GCM, same as game passwords) in app_settings, is write-only (never sent back to a browser,
only "set" and the last 4 characters), and falls back to the NVIDIA_API_KEY / ANTHROPIC_API_KEY environment variables.
"""
import os

import requests

from app import db
from app.models_site import AppSetting
from app.utils.auth import utcnow

PROVIDERS = {
    "nvidia": {"label": "NVIDIA (free endpoint)", "env": "NVIDIA_API_KEY", "prefix": "nvapi-",
               "default_model": "nvidia/nemotron-3.5-lightning-30b-a3b", "base_url": "https://integrate.api.nvidia.com/v1"},
    "anthropic": {"label": "Anthropic Claude", "env": "ANTHROPIC_API_KEY", "prefix": "sk-ant-",
                  "default_model": "claude-haiku-5-5", "base_url": "https://api.anthropic.com/v1"},
}


def _get(key):
    row = db.session.get(AppSetting, key)
    return row.value if row and row.value else None


def _set(key, value, admin_id=None):
    row = db.session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key)
        db.session.add(row)
    row.value, row.updated_at, row.updated_by = value, utcnow(), admin_id


def provider():
    p = _get("assistant.provider") or "nvidia"
    return p if p in PROVIDERS else "nvidia"


def model(p=None):
    p = p or provider()
    return _get(f"assistant.model.{p}") or PROVIDERS[p]["default_model"]


def api_key(p=None):
    """The key in use: the one pasted in the admin panel, else the server environment variable."""
    p = p or provider()
    return _get(f"assistant.key.{p}") or os.getenv(PROVIDERS[p]["env"], "").strip() or None


def key_source(p):
    if _get(f"assistant.key.{p}"):
        return "admin"
    return "env" if os.getenv(PROVIDERS[p]["env"], "").strip() else None


def public_view():
    """What the admin page may see. Never the key itself."""
    out = {"provider": provider(), "providers": {}}
    for p, meta in PROVIDERS.items():
        key = api_key(p)
        out["providers"][p] = {"label": meta["label"], "model": model(p), "default_model": meta["default_model"],
                               "key_set": bool(key), "key_hint": f"…{key[-4:]}" if key else None, "source": key_source(p),
                               "prefix": meta["prefix"]}
    return out


def save(provider_name, model_name=None, key=None, admin_id=None):
    _set("assistant.provider", provider_name, admin_id)
    if model_name is not None:
        _set(f"assistant.model.{provider_name}", model_name or None, admin_id)
    if key:
        _set(f"assistant.key.{provider_name}", key, admin_id)


def remove_key(provider_name, admin_id=None):
    _set(f"assistant.key.{provider_name}", None, admin_id)


def test_connection(p=None):
    """One tiny real request to the provider with the saved key. Returns (ok, message); the message never contains the key."""
    p = p or provider()
    key = api_key(p)
    if not key:
        return False, "No API key saved yet."
    meta = PROVIDERS[p]
    try:
        if p == "anthropic":
            r = requests.post(f"{meta['base_url']}/messages", timeout=25,
                              headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": model(p), "max_tokens": 8, "messages": [{"role": "user", "content": "Reply with: ok"}]})
        else:
            r = requests.post(f"{meta['base_url']}/chat/completions", timeout=25,
                              headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                              json={"model": model(p), "max_tokens": 8, "temperature": 0,
                                    "chat_template_kwargs": {"enable_thinking": False},
                                    "messages": [{"role": "user", "content": "Reply with: ok"}]})
    except requests.RequestException as e:
        return False, f"Could not reach the provider ({type(e).__name__})."
    if r.status_code == 200:
        return True, "Connected. The key and model work."
    if r.status_code in (401, 403):
        return False, "The provider rejected this key (invalid, expired or not allowed for this model)."
    if r.status_code == 404:
        return False, "The provider does not know this model name. Check the model field."
    if r.status_code == 429:
        return False, "Key accepted, but the provider says rate limit or credit used up (HTTP 429)."
    return False, f"The provider answered HTTP {r.status_code}."
