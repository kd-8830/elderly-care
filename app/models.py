from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    role = db.Column(db.String(20), nullable=False, default="elderly")
    passcode_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    memberships = db.relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan"
    )

    def set_passcode(self, passcode: str) -> None:
        self.passcode_hash = generate_password_hash(passcode)

    def check_passcode(self, passcode: str) -> bool:
        return check_password_hash(self.passcode_hash, passcode)

    def __repr__(self):
        return f"<User {self.email}>"


class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    owner_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    owner = db.relationship("User", foreign_keys=[owner_user_id])
    memberships = db.relationship(
        "Membership", back_populates="profile", cascade="all, delete-orphan"
    )
    medications = db.relationship(
        "Medication", back_populates="profile", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Profile {self.name}>"


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (
        db.UniqueConstraint("user_id", "profile_id", name="uq_membership_user_profile"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="family")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    user = db.relationship("User", back_populates="memberships")
    profile = db.relationship("Profile", back_populates="memberships")

    def __repr__(self):
        return f"<Membership u={self.user_id} p={self.profile_id} {self.role}>"


# ----------------- Stage 2 -----------------


class Medication(db.Model):
    __tablename__ = "medications"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(120), nullable=False)
    frequency = db.Column(db.String(60), nullable=False, default="daily")
    # JSON list like ["08:00", "20:00"]
    times = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    profile = db.relationship("Profile", back_populates="medications")
    dose_logs = db.relationship(
        "DoseLog", back_populates="medication", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Medication {self.name} {self.times}>"


class DoseLog(db.Model):
    __tablename__ = "dose_logs"
    __table_args__ = (
        db.UniqueConstraint(
            "medication_id", "scheduled_at", name="uq_dose_med_scheduled"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(
        db.Integer, db.ForeignKey("medications.id"), nullable=False, index=True
    )
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    # pending | taken | missed
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    taken_at = db.Column(db.DateTime(timezone=True), nullable=True)

    medication = db.relationship("Medication", back_populates="dose_logs")

    def __repr__(self):
        return f"<DoseLog med={self.medication_id} at={self.scheduled_at} {self.status}>"