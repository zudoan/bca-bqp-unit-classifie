from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from api.database import Base
from api.models import User


class UserDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "users.db"
        self.engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_users_table_and_unique_indexes_are_created(self) -> None:
        schema = inspect(self.engine)

        self.assertIn("users", schema.get_table_names())
        unique_columns = {
            tuple(constraint["column_names"])
            for constraint in schema.get_unique_constraints("users")
        }
        unique_columns.update(
            tuple(index["column_names"])
            for index in schema.get_indexes("users")
            if index.get("unique")
        )
        self.assertIn(("username",), unique_columns)
        self.assertIn(("email",), unique_columns)

    def test_user_defaults_are_persisted(self) -> None:
        with Session(self.engine) as database:
            user = User(
                username="doanh",
                email="doanh@example.com",
                display_name="Doanh",
                password_hash="not-a-real-password-hash",
            )
            database.add(user)
            database.commit()

            stored_user = database.scalar(select(User).where(User.username == "doanh"))

        self.assertIsNotNone(stored_user)
        assert stored_user is not None
        self.assertEqual(stored_user.role, "user")
        self.assertTrue(stored_user.is_active)
        self.assertIsNotNone(stored_user.created_at)
        self.assertIsNotNone(stored_user.updated_at)
        self.assertIsNone(stored_user.last_login_at)


if __name__ == "__main__":
    unittest.main()
