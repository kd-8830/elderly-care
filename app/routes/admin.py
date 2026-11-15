from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)

from ..models import AuditLog, Profile, Role, SafetyFlag, SymptomLog, db
from ..services.roles import require_membership
from .auth import current_user, login_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/profile/<int:profile_id>/audit")
@login_required
def audit(profile_id):
    user = current_user()
    require_membership(user, profile_id, Role.ALL)
    profile = db.session.get(Profile, profile_id)
    logs = (
        AuditLog.query.filter_by(profile_id=profile_id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("audit.html", profile=profile, logs=logs)


@admin_bp.route("/profile/<int:profile_id>/symptoms", methods=["GET", "POST"])
@login_required
def symptoms(profile_id):
    user = current_user()
    require_membership(user, profile_id, Role.ALL)
    profile = db.session.get(Profile, profile_id)

    if request.method == "POST":
        require_membership(user, profile_id, Role.CAN_EDIT)
        symptom = (request.form.get("symptom") or "").strip()
        if not symptom:
            flash("Describe the symptom.", "error")
        else:
            db.session.add(
                SymptomLog(
                    profile_id=profile_id,
                    logged_by_user_id=user.id,
                    symptom=symptom,
                    severity=(request.form.get("severity") or "mild"),
                    notes=(request.form.get("notes") or "").strip(),
                )
            )
            db.session.commit()
            flash("Symptom logged.", "success")
        return redirect(url_for("admin.symptoms", profile_id=profile_id))

    entries = (
        SymptomLog.query.filter_by(profile_id=profile_id)
        .order_by(SymptomLog.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "symptoms.html", profile=profile, entries=entries,
        can_edit=user.memberships and any(
            m.profile_id == profile_id and m.role in Role.CAN_EDIT
            for m in user.memberships
        ),
    )