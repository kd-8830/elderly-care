from datetime import datetime, timezone

from flask import (
    Blueprint, Response, abort, flash, redirect, render_template, request, url_for,
)

from ..models import Appointment, Doctor, Profile, Role, db
from ..services.roles import require_membership
from .auth import current_user, login_required

appointments_bp = Blueprint("appointments", __name__, url_prefix="/appointments")


def _parse_dt(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        raise ValueError("Date/time must be in YYYY-MM-DDTHH:MM format.")


@appointments_bp.route("/profile/<int:profile_id>")
@login_required
def list_for_profile(profile_id):
    user = current_user()
    membership = require_membership(user, profile_id, Role.CAN_VIEW)
    profile = db.session.get(Profile, profile_id)
    appts = (
        Appointment.query.filter_by(profile_id=profile_id)
        .order_by(Appointment.scheduled_at)
        .all()
    )
    doctors = Doctor.query.filter_by(profile_id=profile_id).order_by(Doctor.name).all()
    return render_template(
        "appointments.html",
        profile=profile,
        appts=appts,
        doctors=doctors,
        membership=membership,
        can_edit=membership.role in Role.CAN_EDIT,
    )


@appointments_bp.route("/profile/<int:profile_id>/doctor/new", methods=["POST"])
@login_required
def add_doctor(profile_id):
    user = current_user()
    require_membership(user, profile_id, Role.CAN_EDIT)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Doctor name is required.", "error")
        return redirect(url_for("appointments.list_for_profile", profile_id=profile_id))
    db.session.add(
        Doctor(
            profile_id=profile_id,
            name=name,
            specialty=(request.form.get("specialty") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
        )
    )
    db.session.commit()
    flash(f"Added doctor {name}.", "success")
    return redirect(url_for("appointments.list_for_profile", profile_id=profile_id))


@appointments_bp.route("/profile/<int:profile_id>/new", methods=["POST"])
@login_required
def create(profile_id):
    user = current_user()
    require_membership(user, profile_id, Role.CAN_EDIT)
    try:
        scheduled_at = _parse_dt(request.form.get("scheduled_at"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("appointments.list_for_profile", profile_id=profile_id))
    doctor_id = request.form.get("doctor_id") or None
    doctor_id = int(doctor_id) if doctor_id else None
    appt = Appointment(
        profile_id=profile_id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at,
        location=(request.form.get("location") or "").strip(),
        notes=(request.form.get("notes") or "").strip(),
    )
    db.session.add(appt)
    db.session.commit()
    flash("Appointment created.", "success")
    return redirect(url_for("appointments.list_for_profile", profile_id=profile_id))


@appointments_bp.route("/<int:appt_id>/delete", methods=["POST"])
@login_required
def delete(appt_id):
    user = current_user()
    appt = db.session.get(Appointment, appt_id)
    if appt is None:
        abort(404)
    require_membership(user, appt.profile_id, Role.CAN_EDIT)
    profile_id = appt.profile_id
    db.session.delete(appt)
    db.session.commit()
    flash("Appointment deleted.", "success")
    return redirect(url_for("appointments.list_for_profile", profile_id=profile_id))


@appointments_bp.route("/<int:appt_id>.ics")
@login_required
def ics(appt_id):
    user = current_user()
    appt = db.session.get(Appointment, appt_id)
    if appt is None:
        abort(404)
    require_membership(user, appt.profile_id, Role.CAN_VIEW)

    dt_fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(dt_fmt)
    dtstart = appt.scheduled_at.astimezone(timezone.utc).strftime(dt_fmt)
    doc = appt.doctor.name if appt.doctor else "Doctor"
    summary = f"Appointment — {doc}"
    description = (appt.notes or "").replace("\n", "\\n")

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//ElderCare//Appointments//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:appt-{appt.id}@eldercare\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART:{dtstart}\r\n"
        "DURATION:PT1H\r\n"
        f"SUMMARY:{summary}\r\n"
        f"LOCATION:{(appt.location or '').replace(',', chr(92) + ',')}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    return Response(
        ics,
        status=200,
        mimetype="text/calendar",
        headers={
            "Content-Type": "text/calendar; charset=utf-8",
            "Content-Disposition": f'attachment; filename="appointment-{appt.id}.ics"',
        },
    )