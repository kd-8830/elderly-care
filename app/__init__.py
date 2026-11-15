from flask import Flask

from .config import Config
from .models import db


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    db.init_app(app)

    from .routes.auth import auth_bp
    from .routes.profiles import profiles_bp
    from .routes.medications import medications_bp
    from .routes.cron import cron_bp
    from .routes.invitations import invitations_bp
    from .routes.appointments import appointments_bp
    from .routes.digests import digests_bp
    from .routes.admin import admin_bp
    from .routes.reports import reports_bp

    for bp in (
        auth_bp, profiles_bp, medications_bp, cron_bp, invitations_bp,
        appointments_bp, digests_bp, admin_bp, reports_bp,
    ):
        app.register_blueprint(bp)

    if app.config.get("AUTO_CREATE_TABLES"):
        with app.app_context():
            db.create_all()

    return app