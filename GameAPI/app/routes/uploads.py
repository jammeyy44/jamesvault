"""Serves uploaded game thumbnails from /uploads/games/<name>. Only files we created are reachable (strict name pattern)."""
import os
import re

from flask import Blueprint, abort, current_app, send_from_directory

uploads_bp = Blueprint('uploads', __name__)
NAME_RE = re.compile(r'^[a-f0-9]{32}\.(png|jpg|webp)$')
MIME = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


def games_dir():
    path = os.path.join(current_app.config["UPLOAD_DIR"], "games")
    os.makedirs(path, exist_ok=True)
    return path


@uploads_bp.route('/uploads/games/<name>')
def game_image(name):
    if not NAME_RE.match(name):
        abort(404)
    resp = send_from_directory(games_dir(), name, mimetype=MIME[name.rsplit(".", 1)[1]], max_age=86400)
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'"  # an image can never run script
    return resp
