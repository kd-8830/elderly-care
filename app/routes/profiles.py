from flask import Blueprint, render_template
from sqlalchemy import text

from ..models import Membership, Profile, db
from ..services.adherence import adherence_for_profile, current_streak
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

    enriched = []
    for membership, profile in rows:
        stats = adherence_for_profile(profile.id)
        stats["streak"] = current_streak(profile.id)
        enriched.append((membership, profile, stats))

    return render_template("dashboard.html", user=user, rows=enriched)


@profiles_bp.route("/healthz")
def healthz():
    try:
        db.session.execute(text("SELECT 1"))
        return {"ok": True}, 200
    except Exception as exc:
        return {"ok": False, "error": str(exc)}, 500