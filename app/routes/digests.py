from flask import Blueprint, abort, render_template

from ..models import Profile, Role, db
from ..services.digests import render_digest_html
from ..services.roles import require_membership
from .auth import current_user, login_required

digests_bp = Blueprint("digests", __name__, url_prefix="/preview")


@digests_bp.route("/digest")
@digests_bp.route("/digest/<int:profile_id>")
@login_required
def digest(profile_id=None):
    user = current_user()
    if profile_id is None:
        membership = user.memberships[0] if user.memberships else None
        if membership is None:
            abort(403)
        profile_id = membership.profile_id
    require_membership(user, profile_id, Role.ALL)
    html = render_digest_html(profile_id, "morning")
    profile = db.session.get(Profile, profile_id)
    return render_template(
        "digest_preview.html", profile=profile, html=html
    )