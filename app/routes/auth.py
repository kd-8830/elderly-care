from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..models import Membership, Profile, User, db

auth_bp = Blueprint("auth", __name__)

VALID_ROLES = {"elderly", "caretaker", "family"}


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profiles.dashboard"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        passcode = request.form.get("passcode") or ""
        role = (request.form.get("role") or "elderly").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if len(passcode) < 4:
            errors.append("Passcode must be at least 4 characters.")
        if role not in VALID_ROLES:
            errors.append("Please choose a valid role.")
        if not errors and User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "register.html", form={"name": name, "email": email, "role": role}
            )

        user = User(name=name, email=email, role=role)
        user.set_passcode(passcode)
        db.session.add(user)
        db.session.flush()  # get user.id

        profile = Profile(
            name=f"{name}'s Care Profile", owner_user_id=user.id
        )
        db.session.add(profile)
        db.session.flush()

        membership = Membership(
            user_id=user.id, profile_id=profile.id, role="owner"
        )
        db.session.add(membership)
        db.session.commit()

        session.clear()
        session["user_id"] = user.id
        flash(f"Welcome, {user.name}!", "success")
        return redirect(url_for("profiles.dashboard"))

    return render_template("register.html", form={"role": "elderly"})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profiles.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        passcode = request.form.get("passcode") or ""

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_passcode(passcode):
            flash("Email or passcode is incorrect.", "error")
            return render_template("login.html", form={"email": email})

        session.clear()
        session["user_id"] = user.id
        flash(f"Welcome back, {user.name}!", "success")
        return redirect(url_for("profiles.dashboard"))

    return render_template("login.html", form={})


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))