from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


class Role:
    OWNER = "owner"
    CARETAKER = "caretaker"
    FAMILY = "family"
    ALL = (OWNER, CARETAKER, FAMILY)
    CAN_EDIT = (OWNER, CARETAKER)
    CAN_VIEW = (OWNER, CARETAKER, FAMILY)


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
    invitations = db.relationship(
        "Invitation", back_populates="profile", cascade="all, delete-orphan"
    )
    doctors = db.relationship(
        "Doctor", back_populates="profile", cascade="all, delete-orphan"
    )
    appointments = db.relationship(
        "Appointment", back_populates="profile", cascade="all, delete-orphan"
    )
    notifications = db.relationship(
        "Notification", back_populates="profile", cascade="all, delete-orphan"
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
    role = db.Column(db.String(20), nullable=False, default=Role.FAMILY)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    user = db.relationship("User", back_populates="memberships")
    profile = db.relationship("Profile", back_populates="memberships")

    def __repr__(self):
        return f"<Membership u={self.user_id} p={self.profile_id} {self.role}>"


class Invitation(db.Model):
    __tablename__ = "invitations"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), nullable=False, unique=True, index=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    role = db.Column(db.String(20), nullable=False, default=Role.FAMILY)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    consumed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    max_uses = db.Column(db.Integer, nullable=False, default=1)
    uses = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship("Profile", back_populates="invitations")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    consumed_by = db.relationship("User", foreign_keys=[consumed_by_user_id])

    def __repr__(self):
        return f"<Invitation {self.code} profile={self.profile_id} role={self.role}>"


class Medication(db.Model):
    __tablename__ = "medications"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(120), nullable=False)
    frequency = db.Column(db.String(60), nullable=False, default="daily")
    times = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, default="")
    drug_class = db.Column(db.String(80), default="")
    pill_count = db.Column(db.Integer, nullable=True)
    refill_threshold = db.Column(db.Integer, nullable=True)
    # pending_approval | approved
    approval_status = db.Column(db.String(30), nullable=False, default="approved")
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
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    taken_at = db.Column(db.DateTime(timezone=True), nullable=True)

    medication = db.relationship("Medication", back_populates="dose_logs")

    def __repr__(self):
        return f"<DoseLog med={self.medication_id} at={self.scheduled_at} {self.status}>"


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    specialty = db.Column(db.String(120), default="")
    phone = db.Column(db.String(60), default="")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    profile = db.relationship("Profile", back_populates="doctors")
    appointments = db.relationship("Appointment", back_populates="doctor")


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    location = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(30), nullable=False, default="scheduled")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    profile = db.relationship("Profile", back_populates="appointments")
    doctor = db.relationship("Doctor", back_populates="appointments")


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        db.UniqueConstraint(
            "profile_id", "type", "reference_id", name="uq_notif_profile_type_ref"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    type = db.Column(db.String(40), nullable=False, index=True)
    reference_id = db.Column(db.Integer, nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    profile = db.relationship("Profile", back_populates="notifications")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    target_type = db.Column(db.String(60), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    user = db.relationship("User")


class SafetyFlag(db.Model):
    __tablename__ = "safety_flags"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    severity = db.Column(db.String(20), nullable=False, default="info")
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)


class SymptomLog(db.Model):
    __tablename__ = "symptom_logs"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True
    )
    logged_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    symptom = db.Column(db.String(200), nullable=False)
    severity = db.Column(db.String(20), default="mild")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    logged_by = db.relationship("User")