"""Morning and weekly digests. Triggered via /api/cron/digests."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..models import (
    Appointment, DoseLog, Medication, Membership, Notification, Profile, Role, db,
)
from ..services.adherence import adherence_for_profile
from .email import send_email

APP_TZ = ZoneInfo("Asia/Kolkata")


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


def _emails_for(profile_id, roles):
    rows = (
        db.session.query(Membership)
        .filter(Membership.profile_id == profile_id)
        .filter(Membership.role.in_(roles))
        .all()
    )
    return [m.user.email for m in rows]


def _todays_schedule(profile_id, now_local):
    start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    doses = (
        DoseLog.query.join(Medication, DoseLog.medication_id == Medication.id)
        .filter(Medication.profile_id == profile_id)
        .filter(DoseLog.scheduled_at >= start_utc)
        .filter(DoseLog.scheduled_at < end_utc)
        .order_by(DoseLog.scheduled_at)
        .all()
    )
    appts = (
        Appointment.query.filter(Appointment.profile_id == profile_id)
        .filter(Appointment.scheduled_at >= start_utc)
        .filter(Appointment.scheduled_at < end_utc)
        .filter(Appointment.status == "scheduled")
        .order_by(Appointment.scheduled_at)
        .all()
    )
    return doses, appts


def render_digest_html(profile_id, kind="morning") -> str:
    """Render digest HTML for preview + email body."""
    now_local = datetime.now(APP_TZ)
    doses, appts = _todays_schedule(profile_id, now_local)
    stats = adherence_for_profile(profile_id)
    profile = db.session.get(Profile, profile_id)

    lines = [
        f"<h1>{profile.name} — {kind.title()} Digest</h1>",
        f"<p>Generated {now_local.strftime('%Y-%m-%d %H:%M')} IST</p>",
        f"<p><strong>7-day adherence:</strong> {stats['percentage']}% "
        f"({stats['taken']}/{stats['total']})</p>",
        "<h2>Today's doses</h2>",
    ]
    if doses:
        lines.append("<ul>")
        for d in doses:
            local = d.scheduled_at.astimezone(APP_TZ)
            lines.append(
                f"<li>{local.strftime('%H:%M')} — {d.medication.name} "
                f"({d.medication.dosage}) — <em>{d.status}</em></li>"
            )
        lines.append("</ul>")
    else:
        lines.append("<p>No doses scheduled today.</p>")

    lines.append("<h2>Appointments</h2>")
    if appts:
        lines.append("<ul>")
        for a in appts:
            local = a.scheduled_at.astimezone(APP_TZ)
            doc = a.doctor.name if a.doctor else "your doctor"
            lines.append(
                f"<li>{local.strftime('%H:%M')} — {doc} @ "
                f"{a.location or 'TBD'}</li>"
            )
        lines.append("</ul>")
    else:
        lines.append("<p>No appointments today.</p>")

    lines.append(
        "<hr><p><em>This app is a reminder aid. It does not provide "
        "medical advice. Always follow your doctor's instructions.</em></p>"
    )
    return "\n".join(lines)


def run_digests(now=None) -> dict:
    now_utc = now or datetime.now(timezone.utc)
    now_local = now_utc.astimezone(APP_TZ)
    stats = {"morning_sent": 0, "weekly_sent": 0}

    # Morning digest: fire at 08:00 local ±10 min window.
    if now_local.hour == 8 and now_local.minute < 15:
        ref = int(now_local.strftime("%Y%m%d"))
        for profile in Profile.query.all():
            if _already_sent(profile.id, "morning_digest", ref):
                continue
            html = render_digest_html(profile.id, "morning")
            for email in _emails_for(profile.id, (Role.OWNER, Role.CARETAKER, Role.FAMILY)):
                send_email(email, f"Morning digest — {profile.name}", html)
            _record(profile.id, "morning_digest", ref)
            stats["morning_sent"] += 1
        db.session.commit()

    # Weekly digest: Sunday 09:00 local ±10 min.
    if now_local.weekday() == 6 and now_local.hour == 9 and now_local.minute < 15:
        iso_year, iso_week, _ = now_local.isocalendar()
        ref = iso_year * 100 + iso_week
        for profile in Profile.query.all():
            if _already_sent(profile.id, "weekly_digest", ref):
                continue
            html = render_digest_html(profile.id, "weekly")
            for email in _emails_for(profile.id, (Role.OWNER, Role.CARETAKER, Role.FAMILY)):
                send_email(email, f"Weekly report — {profile.name}", html)
            _record(profile.id, "weekly_digest", ref)
            stats["weekly_sent"] += 1
        db.session.commit()

    return stats