from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models import Medication, Membership, Profile, User, db  # noqa: E402
from app.services.doses import generate_doses_for_medication  # noqa: E402

DEMO_ACCOUNTS = [
    {"name": "Meera Sharma", "email": "meera@example.com", "passcode": "1234", "role": "elderly"},
    {"name": "Ravi Sharma", "email": "ravi@example.com", "passcode": "1234", "role": "caretaker"},
    {"name": "Anita Sharma", "email": "anita@example.com", "passcode": "1234", "role": "family"},
]


def main():
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
                profile = Profile(name=f"{spec['name']}'s Care Profile", owner_user_id=user.id)
                db.session.add(profile)
                db.session.flush()
                db.session.add(Membership(user_id=user.id, profile_id=profile.id, role="owner"))
                print(f"Created {spec['email']} (passcode {spec['passcode']})")
                if spec["email"] == "meera@example.com":
                    meera_profile = profile
            else:
                print(f"Exists  {spec['email']}")
                if spec["email"] == "meera@example.com":
                    meera_profile = Profile.query.filter_by(owner_user_id=user.id).first()
        db.session.commit()

        # Demo medication for Meera's profile.
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
                print(f"Seeded Metformin for Meera ({created} doses over next 7 days).")
            else:
                print("Metformin already exists for Meera.")

        print("Seed complete.")


if __name__ == "__main__":
    main()