"""Admin (superadmin only): paste and test the voice assistant's AI key. The key is write-only."""
from flask import jsonify, request

from app import db
from app.services import assistant_settings as cfg
from app.utils.auth import admin_required, audit, current_player, json_error, rate_limit

from . import site_bp

A = '/admin'


@site_bp.route(f'{A}/assistant-settings')
@admin_required()
def admin_assistant_get():
    return jsonify(cfg.public_view())


@site_bp.route(f'{A}/assistant-settings', methods=['PUT'])
@admin_required()
@rate_limit('assistant-settings', 30, 3600)
def admin_assistant_put():
    d = request.get_json(silent=True) or {}
    p = str(d.get('provider') or '')
    if p not in cfg.PROVIDERS:
        return json_error("Choose a provider.")
    model = d.get('model')
    if model is not None:
        model = str(model).strip()
        if len(model) > 100 or any(c.isspace() for c in model):
            return json_error("That model name does not look right.")
    key = str(d.get('api_key') or '').strip()
    if key:
        if not (20 <= len(key) <= 400) or any(c.isspace() for c in key):
            return json_error("That does not look like an API key. Paste only the key, with no spaces.")
        prefix = cfg.PROVIDERS[p]["prefix"]
        if not key.startswith(prefix):
            return json_error(f"A {cfg.PROVIDERS[p]['label']} key starts with {prefix}")
    cfg.save(p, model, key or None, current_player().id)
    audit("assistant.settings_update", target=p, detail={"model": model, "key_changed": bool(key)})  # never the key
    db.session.commit()
    return jsonify(cfg.public_view())


@site_bp.route(f'{A}/assistant-settings/key', methods=['DELETE'])
@admin_required()
def admin_assistant_remove_key():
    p = str(request.args.get('provider') or cfg.provider())
    if p not in cfg.PROVIDERS:
        return json_error("Unknown provider.")
    cfg.remove_key(p, current_player().id)
    audit("assistant.key_removed", target=p)
    db.session.commit()
    return jsonify(cfg.public_view())


@site_bp.route(f'{A}/assistant-settings/test', methods=['POST'])
@admin_required()
@rate_limit('assistant-test', 10, 600)
def admin_assistant_test():
    p = str((request.get_json(silent=True) or {}).get('provider') or cfg.provider())
    if p not in cfg.PROVIDERS:
        return json_error("Unknown provider.")
    ok, message = cfg.test_connection(p)
    audit("assistant.key_tested", target=p, detail={"ok": ok})
    db.session.commit()
    return jsonify({"ok": ok, "message": message})
