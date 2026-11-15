from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from ..services.adherence import mark_missed_doses
from ..services.digests import run_digests
from ..services.reminders import run_reminders

cron_bp = Blueprint("cron", __name__, url_prefix="/api/cron")


def require_cron_secret(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = current_app.config.get("CRON_SECRET") or ""
        auth = request.headers.get("Authorization", "")
        token = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
        if not expected or token != expected:
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped


@cron_bp.route("/adherence", methods=["GET", "POST"])
@require_cron_secret
def adherence():
    changed = mark_missed_doses()
    return jsonify({"ok": True, "marked_missed": changed}), 200


@cron_bp.route("/reminders", methods=["GET", "POST"])
@require_cron_secret
def reminders():
    stats = run_reminders()
    return jsonify({"ok": True, **stats}), 200


@cron_bp.route("/digests", methods=["GET", "POST"])
@require_cron_secret
def digests():
    stats = run_digests()
    return jsonify({"ok": True, **stats}), 200