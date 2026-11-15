from datetime import datetime, timezone

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)

from ..models import (
    AuditLog, DoseLog, Medication, Profile, Role, SafetyFlag, db,
)
from ..services.doses import (
    generate_doses_for_medication, generate_doses_for_profile, todays_doses,
)
from ..services.roles import require_membership, require_role
from ..services.safety import scan_profile_safety
from .auth import current_user, login_required

medications_bp = Blueprint("medications", __name__, url_prefix="/medications")


def _parse_times(raw: str):
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


def _opt_int(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _med_or_404(med_id):
    med = db.session.get(Medication, med_id)
    if med is None:
        abort(404)
    return med


def _audit(profile_id, user_id, action, target_type, target_id, detail=""):
    db.session.add(
        AuditLog(
            profile_id=profile_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )


@medications_bp.route("/profile/<int:profile_id>")
@login_required
def list_for_profile(profile_id):
    user = current_user()
    membership = require_membership(user, profile_id, Role.CAN_VIEW)
    profile = db.session.get(Profile, profile_id)
    meds = (
        Medication.query.filter_by(profile_id=profile_id)
        .order_by(Medication.name)
        .all()
    )
    scan_profile_safety(profile_id)
    flags = (
        SafetyFlag.query.filter_by(profile_id=profile_id)
        .order_by(SafetyFlag.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "medications.html",
        profile=profile,
        meds=meds,
        membership=membership,
        can_edit=membership.role in Role.CAN_EDIT,
        flags=flags,
    )


@medications_bp.route("/profile/<int:profile_id>/new", methods=["POST"])
@login_required
@require_role(*Role.CAN_EDIT)
def create(profile_id):
    user = current_user()
    name = (request.form.get("name") or "").strip()
    dosage = (request.form.get("dosage") or "").strip()
    frequency = (request.form.get("frequency") or "daily").strip()
    times_raw = request.form.get("times") or ""
    notes = (request.form.get("notes") or "").strip()
    drug_class = (request.form.get("drug_class") or "").strip()
    pill_count = _opt_int(request.form.get("pill_count"))
    refill_threshold = _opt_int(request.form.get("refill_threshold"))

    if not name or not dosage:
        flash("Medication name and dosage are required.", "error")
        return redirect(url_for("medications.list_for_profile", profile_id=profile_id))
    try:
        times = _parse_times(times_raw)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("medications.list_for_profile", profile_id=profile_id))

    membership = require_membership(user, profile_id, Role.CAN_EDIT)
    approval_status = (
        "pending_approval" if membership.role == Role.CARETAKER else "approved"
    )

    med = Medication(
        profile_id=profile_id, name=name, dosage=dosage, frequency=frequency,
        times=times, notes=notes, drug_class=drug_class, pill_count=pill_count,
        refill_threshold=refill_threshold, approval_status=approval_status,
    )
    db.session.add(med)
    db.session.flush()
    _audit(profile_id, user.id, "medication.create", "Medication", med.id,
           f"{med.name} {med.dosage}")
    db.session.commit()

    created = generate_doses_for_medication(med) if approval_status == "approved" else 0
    scan_profile_safety(profile_id)
    flash(f"Added {med.name}. Generated {created} upcoming dose(s).", "success")
    return redirect(url_for("medications.list_for_profile", profile_id=profile_id))


@medications_bp.route("/<int:med_id>/edit", methods=["POST"])
@login_required
def edit(med_id):
    user = current_user()
    med = _med_or_404(med_id)
    membership = require_membership(user, med.profile_id, Role.CAN_EDIT)

    med.name = (request.form.get("name") or med.name).strip()
    med.dosage = (request.form.get("dosage") or med.dosage).strip()
    med.frequency = (request.form.get("frequency") or med.frequency).strip()
    med.notes = (request.form.get("notes") or "").strip()
    med.drug_class = (request.form.get("drug_class") or "").strip()
    med.pill_count = _opt_int(request.form.get("pill_count"))
    med.refill_threshold = _opt_int(request.form.get("refill_threshold"))

    try:
        med.times = _parse_times(request.form.get("times") or "")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(
            url_for("medications.list_for_profile", profile_id=med.profile_id)
        )

    if membership.role == Role.CARETAKER:
        med.approval_status = "pending_approval"

    _audit(med.profile_id, user.id, "medication.update", "Medication", med.id,
           f"{med.name} {med.dosage}")
    db.session.commit()
    created = generate_doses_for_medication(med) if med.approval_status == "approved" else 0
    scan_profile_safety(med.profile_id)
    flash(f"Updated {med.name}. {created} new dose(s) scheduled.", "success")
    return redirect(
        url_for("medications.list_for_profile", profile_id=med.profile_id)
    )


@medications_bp.route("/<int:med_id>/approve", methods=["POST"])
@login_required
def approve(med_id):
    user = current_user()
    med = _med_or_404(med_id)
    require_membership(user, med.profile_id, (Role.OWNER,))
    med.approval_status = "approved"
    _audit(med.profile_id, user.id, "medication.approve", "Medication", med.id,
           med.name)
    db.session.commit()
    generate_doses_for_medication(med)
    flash(f"Approved {med.name}.", "success")
    return redirect(
        url_for("medications.list_for_profile", profile_id=med.profile_id)
    )


@medications_bp.route("/<int:med_id>/delete", methods=["POST"])
@login_required
def delete(med_id):
    user = current_user()
    med = _med_or_404(med_id)
    require_membership(user, med.profile_id, Role.CAN_EDIT)
    profile_id, name, med_id_ = med.profile_id, med.name, med.id
    db.session.delete(med)
    _audit(profile_id, user.id, "medication.delete", "Medication", med_id_, name)
    db.session.commit()
    flash(f"Deleted {name}.", "success")
    return redirect(url_for("medications.list_for_profile", profile_id=profile_id))


@medications_bp.route("/profile/<int:profile_id>/today")
@login_required
def today(profile_id):
    user = current_user()
    membership = require_membership(user, profile_id, Role.CAN_VIEW)
    profile = db.session.get(Profile, profile_id)
    generate_doses_for_profile(profile_id, days=1)
    doses = todays_doses(profile_id)
    return render_template(
        "today.html",
        profile=profile,
        doses=doses,
        membership=membership,
        can_mark=membership.role in Role.CAN_EDIT,
    )


@medications_bp.route("/dose/<int:dose_id>/take", methods=["POST"])
@login_required
def mark_taken(dose_id):
    user = current_user()
    dose = db.session.get(DoseLog, dose_id)
    if dose is None:
        abort(404)
    require_membership(user, dose.medication.profile_id, Role.CAN_EDIT)
    dose.status = "taken"
    dose.taken_at = datetime.now(timezone.utc)
    if dose.medication.pill_count is not None:
        dose.medication.pill_count = max(0, dose.medication.pill_count - 1)
    db.session.commit()
    flash(f"Marked {dose.medication.name} as taken.", "success")
    return redirect(
        url_for("medications.today", profile_id=dose.medication.profile_id)
    )