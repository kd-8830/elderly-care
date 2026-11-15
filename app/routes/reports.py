from flask import Blueprint, abort, render_template, request

from ..models import (
    Appointment, DoseLog, Medication, Profile, Role, SymptomLog, db,
)
from ..services.adherence import adherence_for_profile
from ..services.roles import require_membership
from .auth import current_user, login_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/profile/<int:profile_id>/doctor-visit")
@login_required
def doctor_visit(profile_id):
    user = current_user()
    require_membership(user, profile_id, Role.ALL)
    profile = db.session.get(Profile, profile_id)
    stats = adherence_for_profile(profile_id, days=30)

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    doses = (
        DoseLog.query.join(Medication, DoseLog.medication_id == Medication.id)
        .filter(Medication.profile_id == profile_id)
        .filter(DoseLog.scheduled_at >= start)
        .filter(DoseLog.status == "missed")
        .order_by(DoseLog.scheduled_at.desc())
        .all()
    )
    symptoms = (
        SymptomLog.query.filter_by(profile_id=profile_id)
        .filter(SymptomLog.created_at >= start)
        .order_by(SymptomLog.created_at.desc())
        .all()
    )
    upcoming = (
        Appointment.query.filter_by(profile_id=profile_id)
        .filter(Appointment.status == "scheduled")
        .order_by(Appointment.scheduled_at)
        .limit(5)
        .all()
    )
    return render_template(
        "doctor_report.html",
        profile=profile,
        stats=stats,
        missed=doses,
        symptoms=symptoms,
        upcoming=upcoming,
        now=now,
        start=start,
    )