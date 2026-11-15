import secrets
from datetime import datetime, timedelta, timezone

from ..models import Invitation, Membership, Role, db

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
DEFAULT_EXPIRY_HOURS = 72


def generate_code() -> str:
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if not Invitation.query.filter_by(code=code).first():
            return code
    raise RuntimeError("Could not generate a unique invite code")


def create_invitation(profile_id, role, created_by_user_id,
                      expires_hours=DEFAULT_EXPIRY_HOURS, max_uses=1) -> Invitation:
    if role not in Role.ALL:
        raise ValueError(f"Invalid role: {role}")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    invite = Invitation(
        code=generate_code(),
        profile_id=profile_id,
        role=role,
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
        max_uses=max_uses,
    )
    db.session.add(invite)
    db.session.commit()
    return invite


def redeem_invitation(code: str, user_id: int):
    code = (code or "").strip().upper()
    if not code:
        raise ValueError("Enter a code.")

    invite = Invitation.query.filter_by(code=code).first()
    if invite is None:
        raise ValueError("That code does not exist.")
    if invite.consumed_at is not None and invite.uses >= invite.max_uses:
        raise ValueError("That code has already been used.")
    if invite.uses >= invite.max_uses:
        raise ValueError("That code has reached its usage limit.")
    if invite.expires_at < datetime.now(timezone.utc):
        raise ValueError("That code has expired.")

    existing = Membership.query.filter_by(
        user_id=user_id, profile_id=invite.profile_id
    ).first()
    if existing is not None:
        raise ValueError("You are already a member of this profile.")

    membership = Membership(
        user_id=user_id, profile_id=invite.profile_id, role=invite.role
    )
    db.session.add(membership)

    invite.uses += 1
    if invite.uses >= invite.max_uses:
        invite.consumed_at = datetime.now(timezone.utc)
        invite.consumed_by_user_id = user_id

    db.session.commit()
    return invite, membership