import os

import redis


class ApplicationConfig:
    SECRET_KEY = os.environ["HIVE_CLAIM_FLASK_APP_SECRET_KEY"]

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv("HIVE_CLAIM_MANAGER_SQLALCHEMY_ECHO", "")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "HIVE_CLAIM_FLASK_APP_DB_PATH", f"sqlite:///{os.path.join('/tmp', 'db.sqlite')}"
    )

    SESSION_TYPE = "redis"
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_REDIS = redis.from_url("redis://127.0.0.1:6379")
    SESSION_COOKIE_NAME = "hive-claim-manager-session"
