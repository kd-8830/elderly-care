"""Adherence calculation and the missed-dose sweeper."""
from datetime import datetime, timedelta, timezone

from ..models import DoseLog, Medication, db

# Grace window: pending doses become missed this many minutes past scheduled_at.
GRACE_MINUTES = 60

# Window used by the 7-day adherence metric.
WINDOW_DAYS = 7


def _utcnow():
    return datetime.now(timezone.utc)


def mark_missed_doses(now: datetime | None = None) -> int:
    """Flip pending doses older than GRACE_MINUTES to missed.

    Idempotent. Returns how many rows changed.
    """
    now = now or _utcnow()
    cutoff = now - timedelta(minutes=GRACE_MINUTES)

    pending = (
        DoseLog.query.filter(DoseLog.status == "pending")
        .filter(DoseLog.scheduled_at <= cutoff)
        .all()
    )
    for dose in pending:
        dose.status = "missed"
        dose.taken_at = None
    if pending:
        db.session.commit()
    return len(pending)


def adherence_for_profile(profile_id: int, days: int = WINDOW_DAYS) -> dict:
    """Return adherence stats for the last `days` days.

    Only counts doses that are "due": taken, missed, or pending-but-past-now.
    Pending doses scheduled in the future don't count against adherence.
    """
    now = _utcnow()
    start = now - timedelta(days=days)

    doses = (
        DoseLog.query.join(Medication, DoseLog.medication_id == Medication.id)
        .filter(Medication.profile_id == profile_id)
        .filter(DoseLog.scheduled_at >= start)
        .filter(DoseLog.scheduled_at <= now)
        .all()
    )

    total = len(doses)
    taken = sum(1 for d in doses if d.status == "taken")
    missed = sum(1 for d in doses if d.status == "missed")
    pending = sum(1 for d in doses if d.status == "pending")

    percentage = round((taken / total) * 100) if total else 0

    return {
        "total": total,
        "taken": taken,
        "missed": missed,
        "pending": pending,
        "percentage": percentage,
        "window_days": days,
    }


def current_streak(profile_id: int) -> int:
    """Consecutive days ending today (or yesterday) with no missed doses.

    A day "counts" as good if it has at least one dose and zero missed doses.
    Looks back up to 60 days.
    """
    now = _utcnow()
    today = now.date()

    # Gather statuses grouped by day for the last 60 days.
    start = now - timedelta(days=60)
    doses = (
        DoseLog.query.join(Medication, DoseLog.medication_id == Medication.id)
        .filter(Medication.profile_id == profile_id)
        .filter(DoseLog.scheduled_at >= start)
        .filter(DoseLog.scheduled_at <= now)
        .all()
    )

    per_day: dict = {}
    for dose in doses:
        d = dose.scheduled_at.date()
        bucket = per_day.setdefault(d, {"total": 0, "missed": 0})
        bucket["total"] += 1
        if dose.status == "missed":
            bucket["missed"] += 1

    streak = 0
    # Skip today if it has no doses yet (streak still counts from yesterday).
    cursor = today
    if cursor not in per_day:
        cursor = today - timedelta(days=1)

    for _ in range(60):
        bucket = per_day.get(cursor)
        if bucket is None or bucket["total"] == 0:
            break
        if bucket["missed"] > 0:
            break
        streak += 1
        cursor -= timedelta(days=1)
    return streak