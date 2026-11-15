"""Dose generation and scheduling helpers."""
from datetime import date, datetime, time, timedelta, timezone

from ..models import DoseLog, Medication, db

# How many days ahead to pre-generate dose logs.
GENERATE_DAYS = 7


def _local_tz():
    # Stage 2 uses UTC for storage; Stage 3+ introduces per-profile TZ.
    return timezone.utc


def _combine_local_date_time(d: date, hhmm: str) -> datetime:
    hh, mm = (int(p) for p in hhmm.split(":"))
    naive = datetime.combine(d, time(hour=hh, minute=mm))
    return naive.replace(tzinfo=_local_tz())


def generate_doses_for_medication(med: Medication, days: int = GENERATE_DAYS) -> int:
    """Create DoseLog rows for the next `days` days. Idempotent.

    Returns the number of new rows created.
    """
    if not med.times:
        return 0

    today = datetime.now(_local_tz()).date()
    created = 0
    for offset in range(days):
        d = today + timedelta(days=offset)
        for hhmm in med.times:
            scheduled = _combine_local_date_time(d, hhmm)
            exists = (
                db.session.query(DoseLog.id)
                .filter_by(medication_id=med.id, scheduled_at=scheduled)
                .first()
            )
            if exists:
                continue
            db.session.add(
                DoseLog(
                    medication_id=med.id,
                    scheduled_at=scheduled,
                    status="pending",
                )
            )
            created += 1
    if created:
        db.session.commit()
    return created


def generate_doses_for_profile(profile_id: int, days: int = GENERATE_DAYS) -> int:
    meds = Medication.query.filter_by(profile_id=profile_id).all()
    total = 0
    for med in meds:
        total += generate_doses_for_medication(med, days=days)
    return total


def todays_doses(profile_id: int):
    """Return today's dose logs for a profile, ordered by time."""
    now = datetime.now(_local_tz())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return (
        DoseLog.query.join(Medication, DoseLog.medication_id == Medication.id)
        .filter(Medication.profile_id == profile_id)
        .filter(DoseLog.scheduled_at >= start)
        .filter(DoseLog.scheduled_at < end)
        .order_by(DoseLog.scheduled_at)
        .all()
    )