import os
from typing import Optional

from pyaml_env import parse_config
from sqlalchemy import insert, select

from app import app, bcrypt

from models import db, User


class UsersDB:
    TABLE = User

    def get_user(self, name: str) -> Optional[User]:
        with db.session() as _session:
            return _session.scalars(select(self.TABLE).where(self.TABLE.name == name)).first()

    def create_users(self) -> None:
        with db.session() as _session:
            for user_data in parse_config(os.environ["HIVE_CLAIM_FLASK_APP_USERS_FILE"])["users"]:
                username, password = user_data.split(":")
                app.logger.info(f"Creating user {username}")
                hashed_password = bcrypt.generate_password_hash(password)

                _session.execute(
                    insert(self.TABLE).values(
                        name=username,
                        password=hashed_password,
                        admin=os.getenv("HIVE_CLAIM_MANAGER_SUPERUSER_NAME") == username,
                    )
                )

                _session.commit()

    def delete_table(self) -> None:
        app.logger.info(f"Deleting {self.TABLE.__tablename__} table")
        with db.session() as _session:
            self.TABLE.__table__.drop(bind=db.engine, checkfirst=True)
            _session.commit()
