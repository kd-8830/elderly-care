from datetime import datetime, timezone

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)

from ..models import Invitation, Profile, Role, db
from ..services.invitations import create_invitation, redeem_invitation
from ..services.roles import require_membership
from .auth import current_user, login_required

invitations_bp = Blueprint("invitations", __name__, url_prefix="/invitations")
GENERATE_ROLES = (Role.OWNER, Role.CARETAKER)


@invitations_bp.route("/join", methods=["GET", "POST"])
@login_required
def join():
    user = current_user()
    if request.method == "POST":
        code = request.form.get("code") or ""
        try:
            invite, membership = redeem_invitation(code, user.id)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("join.html", code=code)
        flash(f"Joined {invite.profile.name} as {membership.role}.", "success")
        return redirect(url_for("profiles.dashboard"))
    return render_template("join.html", code="")


@invitations_bp.route("/profile/<int:profile_id>")
@login_required
def list_for_profile(profile_id):
    user = current_user()
    membership = require_membership(user, profile_id, Role.ALL)
    profile = db.session.get(Profile, profile_id)
    invites = (
        Invitation.query.filter_by(profile_id=profile_id)
        .order_by(Invitation.created_at.desc())
        .all()
    )
    return render_template(
        "invitations.html",
        profile=profile,
        invites=invites,
        membership=membership,
        can_generate=membership.role in GENERATE_ROLES,
        now_dt=datetime.now(timezone.utc),
    )


@invitations_bp.route("/profile/<int:profile_id>/new", methods=["POST"])
@login_required
def create(profile_id):
    user = current_user()
    require_membership(user, profile_id, GENERATE_ROLES)
    role = (request.form.get("role") or Role.FAMILY).strip()
    try:
        expires_hours = int(request.form.get("expires_hours") or 72)
    except ValueError:
        expires_hours = 72
    try:
        invite = create_invitation(profile_id, role, user.id, expires_hours, 1)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("invitations.list_for_profile", profile_id=profile_id))
    flash(
        f"Invite code {invite.code} created for {invite.role}, expires in {expires_hours}h.",
        "success",
    )
    return redirect(url_for("invitations.list_for_profile", profile_id=profile_id))


@invitations_bp.route("/<int:invite_id>/revoke", methods=["POST"])
@login_required
def revoke(invite_id):
    user = current_user()
    invite = db.session.get(Invitation, invite_id)
    if invite is None:
        abort(404)
    require_membership(user, invite.profile_id, GENERATE_ROLES)
    invite.consumed_at = invite.expires_at
    db.session.commit()
    flash(f"Invite {invite.code} revoked.", "success")
    return redirect(
        url_for("invitations.list_for_profile", profile_id=invite.profile_id)
    )