from flask import Blueprint, render_template
from sqlalchemy import text

from ..models import Membership, Profile, db
from .auth import current_user, login_required

profiles_bp = Blueprint("profiles", __name__)


@profiles_bp.route("/")
@profiles_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    rows = (
        db.session.query(Membership, Profile)
        .join(Profile, Membership.profile_id == Profile.id)
        .filter(Membership.user_id == user.id)
        .order_by(Profile.name)
        .all()
    )
    return render_template("dashboard.html", user=user, rows=rows)


@profiles_bp.route("/healthz")
def healthz():
    try:
        db.session.execute(text("SELECT 1"))
        return {"ok": True}, 200
    except Exception as exc:  # pragma: no cover - diagnostics only
        return {"ok": False, "error": str(exc)}, 500