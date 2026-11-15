from functools import wraps

from flask import abort, redirect, url_for

from ..models import Membership


def get_membership(user_id: int, profile_id: int):
    return Membership.query.filter_by(user_id=user_id, profile_id=profile_id).first()


def require_membership(user, profile_id: int, allowed_roles=None) -> Membership:
    if user is None:
        abort(403)
    m = get_membership(user.id, profile_id)
    if m is None:
        abort(403)
    if allowed_roles is not None and m.role not in allowed_roles:
        abort(403)
    return m


def require_role(*allowed_roles, param="profile_id"):
    allowed = set(allowed_roles)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            from ..routes.auth import current_user

            user = current_user()
            if user is None:
                return redirect(url_for("auth.login"))
            profile_id = kwargs.get(param)
            if profile_id is None:
                abort(400)
            require_membership(user, profile_id, allowed)
            return view(*args, **kwargs)

        return wrapped

    return decorator