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

    app.register_blueprint(auth_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(medications_bp)
    app.register_blueprint(cron_bp)

    if app.config.get("AUTO_CREATE_TABLES"):
        with app.app_context():
            db.create_all()

    return app