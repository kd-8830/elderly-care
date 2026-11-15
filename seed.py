"""Seed demo data. Run `python seed.py` for baseline, or `python seed.py --backfill`
to also create some past missed doses so adherence < 100% right away."""
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models import DoseLog, Medication, Membership, Profile, User, db  # noqa: E402
from app.services.doses import generate_doses_for_medication  # noqa: E402

DEMO_ACCOUNTS = [
    {"name": "Meera Sharma", "email": "meera@example.com", "passcode": "1234", "role": "elderly"},
    {"name": "Ravi Sharma", "email": "ravi@example.com", "passcode": "1234", "role": "caretaker"},
    {"name": "Anita Sharma", "email": "anita@example.com", "passcode": "1234", "role": "family"},
]


def backfill_history(med: Medication, days: int = 5):
    """Create past dose logs, mixing taken and missed, for adherence testing."""
    now = datetime.now(timezone.utc)
    created = 0
    for offset in range(days, 0, -1):
        day = now - timedelta(days=offset)
        for idx, hhmm in enumerate(med.times or []):
            hh, mm = (int(p) for p in hhmm.split(":"))
            scheduled = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
            exists = (
                db.session.query(DoseLog.id)
                .filter_by(medication_id=med.id, scheduled_at=scheduled)
                .first()
            )
            if exists:
                continue
            # Alternate taken/missed per time slot so adherence sits around 70-80%.
            status = "taken" if (offset + idx) % 3 != 0 else "missed"
            taken_at = scheduled + timedelta(minutes=10) if status == "taken" else None
            db.session.add(
                DoseLog(
                    medication_id=med.id,
                    scheduled_at=scheduled,
                    status=status,
                    taken_at=taken_at,
                )
            )
            created += 1
    if created:
        db.session.commit()
    return created


def main():
    do_backfill = "--backfill" in sys.argv

    app = create_app()
    with app.app_context():
        db.create_all()

        meera_profile = None
        for spec in DEMO_ACCOUNTS:
            user = User.query.filter_by(email=spec["email"]).first()
            if user is None:
                user = User(name=spec["name"], email=spec["email"], role=spec["role"])
                user.set_passcode(spec["passcode"])
                db.session.add(user)
                db.session.flush()
                profile = Profile(
                    name=f"{spec['name']}'s Care Profile", owner_user_id=user.id
                )
                db.session.add(profile)
                db.session.flush()
                db.session.add(
                    Membership(user_id=user.id, profile_id=profile.id, role="owner")
                )
                print(f"Created {spec['email']} (passcode {spec['passcode']})")
                if spec["email"] == "meera@example.com":
                    meera_profile = profile
            else:
                print(f"Exists  {spec['email']}")
                if spec["email"] == "meera@example.com":
                    meera_profile = Profile.query.filter_by(
                        owner_user_id=user.id
                    ).first()
        db.session.commit()

        if meera_profile:
            existing = Medication.query.filter_by(
                profile_id=meera_profile.id, name="Metformin"
            ).first()
            if existing is None:
                med = Medication(
                    profile_id=meera_profile.id,
                    name="Metformin",
                    dosage="500 mg",
                    frequency="daily",
                    times=["08:00", "20:00"],
                    notes="Take with food",
                )
                db.session.add(med)
                db.session.commit()
                created = generate_doses_for_medication(med)
                print(f"Seeded Metformin for Meera ({created} future doses).")
            else:
                med = existing
                print("Metformin already exists for Meera.")

            if do_backfill:
                added = backfill_history(med, days=5)
                print(f"Backfilled {added} historical doses (mix of taken/missed).")

        print("Seed complete.")


if __name__ == "__main__":
    main()