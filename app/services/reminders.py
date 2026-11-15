"""Reminders + escalation. Idempotent via Notification unique constraint."""
from datetime import datetime, timedelta, timezone

from ..models import (
    Appointment, DoseLog, Medication, Membership, Notification, Profile, Role, db,
)
from .email import send_email


def _already_sent(profile_id, ntype, reference_id) -> bool:
    return (
        Notification.query.filter_by(
            profile_id=profile_id, type=ntype, reference_id=reference_id
        ).first()
        is not None
    )


def _record(profile_id, ntype, reference_id):
    db.session.add(
        Notification(profile_id=profile_id, type=ntype, reference_id=reference_id)
    )


def _members_emails(profile_id, roles):
    rows = (
        db.session.query(Membership)
        .filter(Membership.profile_id == profile_id)
        .filter(Membership.role.in_(roles))
        .all()
    )
    return [m.user.email for m in rows]


def _owner_email(profile_id):
    profile = db.session.get(Profile, profile_id)
    return [profile.owner.email] if profile and profile.owner else []


def run_reminders(now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    stats = {"dose_before": 0, "appt_24h": 0, "appt_1h": 0,
             "escalate_30m": 0, "escalate_family": 0}

    # ---- Dose reminders 15 min before ----
    window_start = now + timedelta(minutes=14)
    window_end = now + timedelta(minutes=16)
    upcoming = (
        DoseLog.query.filter(DoseLog.status == "pending")
        .filter(DoseLog.scheduled_at >= window_start)
        .filter(DoseLog.scheduled_at <= window_end)
        .all()
    )
    for dose in upcoming:
        pid = dose.medication.profile_id
        if _already_sent(pid, "dose_reminder_15m", dose.id):
            continue
        recipients = _owner_email(pid)
        body = (
            f"Upcoming dose at {dose.scheduled_at.strftime('%H:%M')} UTC:\n"
            f"  {dose.medication.name} — {dose.medication.dosage}\n"
            "This app is a reminder aid, not medical advice."
        )
        for email in recipients:
            send_email(email, f"Upcoming dose: {dose.medication.name}", body)
        _record(pid, "dose_reminder_15m", dose.id)
        stats["dose_before"] += 1
    db.session.commit()

    # ---- Appointment reminders 24h / 1h ----
    for label, delta, key in (
        ("appt_reminder_24h", timedelta(hours=23, minutes=59), "appt_24h"),
        ("appt_reminder_1h", timedelta(minutes=59), "appt_1h"),
    ):
        window_start = now + delta
        window_end = window_start + timedelta(minutes=2)
        appts = (
            Appointment.query.filter(Appointment.status == "scheduled")
            .filter(Appointment.scheduled_at >= window_start)
            .filter(Appointment.scheduled_at <= window_end)
            .all()
        )
        for appt in appts:
            if _already_sent(appt.profile_id, label, appt.id):
                continue
            recipients = _members_emails(
                appt.profile_id, (Role.OWNER, Role.CARETAKER, Role.FAMILY)
            )
            doc = appt.doctor.name if appt.doctor else "your doctor"
            body = (
                f"Appointment reminder:\n"
                f"  {doc} on {appt.scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC\n"
                f"  Location: {appt.location or 'TBD'}\n"
                f"  Notes: {appt.notes or '—'}"
            )
            for email in recipients:
                send_email(email, "Upcoming appointment", body)
            _record(appt.profile_id, label, appt.id)
            stats[key] += 1
    db.session.commit()

    # ---- Escalation: pending dose 30+ min past scheduled ----
    cutoff = now - timedelta(minutes=30)
    overdue = (
        DoseLog.query.filter(DoseLog.status == "pending")
        .filter(DoseLog.scheduled_at <= cutoff)
        .filter(DoseLog.scheduled_at >= cutoff - timedelta(hours=2))
        .all()
    )
    per_profile_misses = {}
    for dose in overdue:
        pid = dose.medication.profile_id
        if _already_sent(pid, "escalation_caretaker_30m", dose.id):
            continue
        recipients = _members_emails(pid, (Role.CARETAKER,))
        body = (
            f"Missed dose alert:\n"
            f"  {dose.medication.name} was scheduled at "
            f"{dose.scheduled_at.strftime('%H:%M')} UTC and is still pending.\n"
            "Please check in with the person in your care."
        )
        for email in recipients:
            send_email(email, f"Missed dose: {dose.medication.name}", body)
        _record(pid, "escalation_caretaker_30m", dose.id)
        stats["escalate_30m"] += 1
        per_profile_misses.setdefault(pid, 0)
    db.session.commit()

    # ---- Escalation: 2+ missed doses today → family ----
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    missed_today = (
        DoseLog.query.filter(DoseLog.status == "missed")
        .filter(DoseLog.scheduled_at >= day_start)
        .all()
    )
    counts = {}
    for dose in missed_today:
        pid = dose.medication.profile_id
        counts[pid] = counts.get(pid, 0) + 1

    for pid, count in counts.items():
        if count < 2:
            continue
        ref = int(now.strftime("%Y%m%d"))
        if _already_sent(pid, "escalation_family_2missed", ref):
            continue
        recipients = _members_emails(pid, (Role.FAMILY,))
        body = (
            f"{count} missed doses today on this profile.\n"
            "Consider reaching out to the person in your care."
        )
        for email in recipients:
            send_email(email, "Family alert: multiple missed doses", body)
        _record(pid, "escalation_family_2missed", ref)
        stats["escalate_family"] += 1
    db.session.commit()

    return stats