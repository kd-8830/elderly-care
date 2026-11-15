import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models import (  # noqa: E402
    Appointment, DoseLog, Doctor, Medication, Membership, Profile,
    SymptomLog, User, db,
)
from app.services.doses import generate_doses_for_medication  # noqa: E402

DEMO_ACCOUNTS = [
    {"name": "Meera Sharma", "email": "meera@example.com", "passcode": "1234", "role": "elderly"},
    {"name": "Ravi Sharma", "email": "ravi@example.com", "passcode": "1234", "role": "caretaker"},
    {"name": "Anita Sharma", "email": "anita@example.com", "passcode": "1234", "role": "family"},
]


def backfill_history(med, days=5):
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
            status = "taken" if (offset + idx) % 3 != 0 else "missed"
            taken_at = scheduled + timedelta(minutes=10) if status == "taken" else None
            db.session.add(DoseLog(
                medication_id=med.id, scheduled_at=scheduled,
                status=status, taken_at=taken_at,
            ))
            created += 1
    if created:
        db.session.commit()
    return created


def main():
    do_backfill = "--backfill" in sys.argv
    app = create_app()
    with app.app_context():
        db.create_all()

        profiles = {}
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
                db.session.add(Membership(
                    user_id=user.id, profile_id=profile.id, role="owner",
                ))
                print(f"Created {spec['email']} (passcode {spec['passcode']})")
                profiles[spec["email"]] = (user, profile)
            else:
                profile = Profile.query.filter_by(owner_user_id=user.id).first()
                profiles[spec["email"]] = (user, profile)
                print(f"Exists  {spec['email']}")
        db.session.commit()

        meera_user, meera_profile = profiles["meera@example.com"]

        # Medications on Meera's profile
        metformin = Medication.query.filter_by(
            profile_id=meera_profile.id, name="Metformin"
        ).first()
        if metformin is None:
            metformin = Medication(
                profile_id=meera_profile.id, name="Metformin", dosage="500 mg",
                frequency="daily", times=["08:00", "20:00"],
                notes="Take with food", drug_class="biguanide",
                pill_count=20, refill_threshold=10,
            )
            db.session.add(metformin)
            db.session.commit()
            generate_doses_for_medication(metformin)
            print("Seeded Metformin for Meera.")

        if do_backfill:
            n = backfill_history(metformin, days=5)
            print(f"Backfilled {n} historical doses.")

        # Doctor + appointment
        doctor = Doctor.query.filter_by(profile_id=meera_profile.id).first()
        if doctor is None:
            doctor = Doctor(
                profile_id=meera_profile.id, name="Dr. Rao",
                specialty="Cardiologist", phone="+91 98765 43210",
            )
            db.session.add(doctor)
            db.session.commit()

        if Appointment.query.filter_by(profile_id=meera_profile.id).first() is None:
            appt_time = datetime.now(timezone.utc) + timedelta(days=2, hours=3)
            db.session.add(Appointment(
                profile_id=meera_profile.id, doctor_id=doctor.id,
                scheduled_at=appt_time, location="Apollo Clinic, Room 4",
                notes="Bring recent BP readings",
            ))
            db.session.commit()
            print(f"Seeded appointment with Dr. Rao on {appt_time.isoformat()}.")

        if SymptomLog.query.filter_by(profile_id=meera_profile.id).first() is None:
            db.session.add(SymptomLog(
                profile_id=meera_profile.id, logged_by_user_id=meera_user.id,
                symptom="Mild dizziness", severity="mild",
                notes="After morning walk",
            ))
            db.session.commit()
            print("Seeded symptom log for Meera.")

        print("Seed complete.")


if __name__ == "__main__":
    main()