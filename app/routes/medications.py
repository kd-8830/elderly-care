from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import text

from ..models import DoseLog, Medication, Membership, Profile, db
from ..services.doses import (
    generate_doses_for_medication,
    generate_doses_for_profile,
    todays_doses,
)
from .auth import current_user, login_required

medications_bp = Blueprint("medications", __name__, url_prefix="/medications")

EDIT_ROLES = {"owner", "caretaker"}
VIEW_ROLES = {"owner", "caretaker", "family"}


# ----------------- helpers -----------------


def _membership_or_403(profile_id: int, allowed_roles) -> Membership:
    user = current_user()
    membership = Membership.query.filter_by(
        user_id=user.id, profile_id=profile_id
    ).first()
    if membership is None:
        abort(403)
    if allowed_roles and membership.role not in allowed_roles:
        abort(403)
    return membership


def _parse_times(raw: str):
    """Parse 'HH:MM, HH:MM' into a sorted unique list. Raises ValueError."""
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    if not parts:
        raise ValueError("Enter at least one time (e.g. 08:00, 20:00).")
    cleaned = []
    for p in parts:
        try:
            datetime.strptime(p, "%H:%M")
        except ValueError:
            raise ValueError(f"'{p}' is not a valid HH:MM time.")
        if p not in cleaned:
            cleaned.append(p)
    return sorted(cleaned)


def _medication_or_404(med_id: int) -> Medication:
    med = db.session.get(Medication, med_id)
    if med is None:
        abort(404)
    return med


# ----------------- list + create -----------------


@medications_bp.route("/profile/<int:profile_id>")
@login_required
def list_for_profile(profile_id):
    membership = _membership_or_403(profile_id, VIEW_ROLES)
    profile = db.session.get(Profile, profile_id)
    meds = (
        Medication.query.filter_by(profile_id=profile_id)
        .order_by(Medication.name)
        .all()
    )
    return render_template(
        "medications.html",
        profile=profile,
        meds=meds,
        membership=membership,
        can_edit=membership.role in EDIT_ROLES,
    )


@medications_bp.route("/profile/<int:profile_id>/new", methods=["POST"])
@login_required
def create(profile_id):
    _membership_or_403(profile_id, EDIT_ROLES)

    name = (request.form.get("name") or "").strip()
    dosage = (request.form.get("dosage") or "").strip()
    frequency = (request.form.get("frequency") or "daily").strip()
    times_raw = request.form.get("times") or ""
    notes = (request.form.get("notes") or "").strip()

    if not name or not dosage:
        flash("Medication name and dosage are required.", "error")
        return redirect(url_for("medications.list_for_profile", profile_id=profile_id))

    try:
        times = _parse_times(times_raw)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("medications.list_for_profile", profile_id=profile_id))

    med = Medication(
        profile_id=profile_id,
        name=name,
        dosage=dosage,
        frequency=frequency,
        times=times,
        notes=notes,
    )
    db.session.add(med)
    db.session.commit()

    created = generate_doses_for_medication(med)
    flash(
        f"Added {med.name}. Generated {created} upcoming dose(s).", "success"
    )
    return redirect(url_for("medications.list_for_profile", profile_id=profile_id))


# ----------------- edit -----------------


@medications_bp.route("/<int:med_id>/edit", methods=["POST"])
@login_required
def edit(med_id):
    med = _medication_or_404(med_id)
    _membership_or_403(med.profile_id, EDIT_ROLES)

    med.name = (request.form.get("name") or med.name).strip()
    med.dosage = (request.form.get("dosage") or med.dosage).strip()
    med.frequency = (request.form.get("frequency") or med.frequency).strip()
    med.notes = (request.form.get("notes") or "").strip()

    times_raw = request.form.get("times") or ""
    try:
        med.times = _parse_times(times_raw)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(
            url_for("medications.list_for_profile", profile_id=med.profile_id)
        )

    db.session.commit()
    # Regenerate upcoming doses (idempotent for existing times).
    created = generate_doses_for_medication(med)
    flash(f"Updated {med.name}. {created} new dose(s) scheduled.", "success")
    return redirect(
        url_for("medications.list_for_profile", profile_id=med.profile_id)
    )


# ----------------- delete -----------------


@medications_bp.route("/<int:med_id>/delete", methods=["POST"])
@login_required
def delete(med_id):
    med = _medication_or_404(med_id)
    _membership_or_403(med.profile_id, EDIT_ROLES)
    profile_id = med.profile_id
    name = med.name
    db.session.delete(med)
    db.session.commit()
    flash(f"Deleted {name}.", "success")
    return redirect(url_for("medications.list_for_profile", profile_id=profile_id))


# ----------------- today -----------------


@medications_bp.route("/profile/<int:profile_id>/today")
@login_required
def today(profile_id):
    membership = _membership_or_403(profile_id, VIEW_ROLES)
    profile = db.session.get(Profile, profile_id)

    # Make sure today's doses exist even if the user just added a medication.
    generate_doses_for_profile(profile_id, days=1)

    doses = todays_doses(profile_id)
    return render_template(
        "today.html",
        profile=profile,
        doses=doses,
        membership=membership,
        can_mark=membership.role in EDIT_ROLES,
    )


@medications_bp.route("/dose/<int:dose_id>/take", methods=["POST"])
@login_required
def mark_taken(dose_id):
    dose = db.session.get(DoseLog, dose_id)
    if dose is None:
        abort(404)
    _membership_or_403(dose.medication.profile_id, EDIT_ROLES)

    from datetime import timezone as _tz

    dose.status = "taken"
    dose.taken_at = datetime.now(_tz.utc)
    db.session.commit()
    flash(f"Marked {dose.medication.name} as taken.", "success")
    return redirect(
        url_for("medications.today", profile_id=dose.medication.profile_id)
    )