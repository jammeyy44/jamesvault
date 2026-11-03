"""Voice assistant API for signed-in players. The AI only answers and proposes; see app/services/assistant.py."""
from flask import jsonify, request

from app import db
from app.services import assistant, assistant_llm, assistant_settings as settings
from app.utils.auth import audit, current_player, json_error, player_required, rate_limit

from . import site_bp


@site_bp.route('/assistant/status')
@player_required
def assistant_status():
    return jsonify({"enabled": bool(settings.api_key())})


@site_bp.route('/assistant/chat', methods=['POST'])
@player_required
@rate_limit('assistant', 40, 600)
def assistant_chat():
    player = current_player()
    if not settings.api_key():
        return json_error("The assistant is not set up yet.", 503, code="assistant_off")
    history = assistant.clean_history((request.get_json(silent=True) or {}).get('messages'))
    while history and history[0]["role"] != "user":
        history.pop(0)
    if not history or history[-1]["role"] != "user":
        return json_error("Say or type something first.")
    try:
        result = assistant.converse(player, history)
    except assistant_llm.AssistantUnavailable:
        return json_error("The assistant is unavailable right now. Please try again in a moment.", 502, code="assistant_unavailable")
    audit("assistant.chat", detail={"proposals": [p["type"] for p in result["proposals"]], "actions": [a["type"] for a in result["actions"]]})  # never the words
    db.session.commit()
    return jsonify(result)
