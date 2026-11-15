import os


def _normalize_database_url(url: str) -> str:
    """Make hosted Postgres URLs work with SQLAlchemy + psycopg2."""
    if not url:
        # Local-only fallback. Production must set DATABASE_URL.
        return "sqlite:///elderly_care.db"
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.environ.get("DATABASE_URL", "")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Serverless-safe pool settings: cheap, self-healing connections.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    CRON_SECRET = os.environ.get("CRON_SECRET", "dev-cron-secret")
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")
    AUTO_CREATE_TABLES = os.environ.get("AUTO_CREATE_TABLES", "1") == "1"