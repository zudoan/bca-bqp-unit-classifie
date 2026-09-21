from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("CORS_ORIGINS", "https://bca-bqp-frontend.onrender.com/")

from api.admin import ensure_bootstrap_admin
from api.database import Base, get_database
from api.main import app
from api.models import User, UserSession
from api.security import hash_password, verify_password


class AdminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "admin-test.db"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        def override_database():
            database = self.session_factory()
            try:
                yield database
            finally:
                database.close()

        app.dependency_overrides[get_database] = override_database
        self.admin = self._create_user("admin", "admin@example.com", role="admin")
        self.member = self._create_user("member", "member@example.com")
        self.admin_client = TestClient(app)
        self.member_client = TestClient(app)
        self._login(self.admin_client, "admin")
        self._login(self.member_client, "member")

    def tearDown(self) -> None:
        self.admin_client.close()
        self.member_client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def _create_user(self, username: str, email: str, *, role: str = "user") -> User:
        with self.session_factory() as database:
            user = User(
                username=username,
                email=email,
                display_name=username.title(),
                password_hash=hash_password("Matkhau123"),
                role=role,
            )
            database.add(user)
            database.commit()
            database.refresh(user)
            return user

    def _login(self, client: TestClient, username: str) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Matkhau123", "remember": True},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_regular_user_cannot_open_admin_api(self) -> None:
        response = self.member_client.get("/api/v1/admin/users")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_filter_and_update_users(self) -> None:
        list_response = self.admin_client.get("/api/v1/admin/users", params={"query": "member"})
        self.assertEqual(list_response.status_code, 200, list_response.text)
        payload = list_response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["username"], "member")
        self.assertEqual(payload["active_count"], 2)
        self.assertEqual(payload["admin_count"], 1)

        update_response = self.admin_client.patch(
            f"/api/v1/admin/users/{self.member.id}",
            json={"display_name": "Thành viên kiểm thử", "role": "admin"},
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        self.assertEqual(update_response.json()["role"], "admin")
        self.assertEqual(update_response.json()["display_name"], "Thành viên kiểm thử")

    def test_admin_cannot_remove_own_admin_access(self) -> None:
        response = self.admin_client.patch(
            f"/api/v1/admin/users/{self.admin.id}",
            json={"role": "user"},
        )
        self.assertEqual(response.status_code, 409)

    def test_deactivate_user_revokes_existing_sessions(self) -> None:
        response = self.admin_client.delete(f"/api/v1/admin/users/{self.member.id}")
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(self.member_client.get("/api/v1/auth/me").status_code, 401)

        with self.session_factory() as database:
            stored_user = database.get(User, self.member.id)
            active_sessions = database.scalar(
                select(func.count()).select_from(UserSession).where(
                    UserSession.user_id == self.member.id,
                    UserSession.revoked_at.is_(None),
                )
            )
        self.assertIsNotNone(stored_user)
        assert stored_user is not None
        self.assertFalse(stored_user.is_active)
        self.assertEqual(active_sessions, 0)

    def test_environment_can_bootstrap_exactly_one_admin(self) -> None:
        environment = {
            "ADMIN_USERNAME": "bootstrap.admin",
            "ADMIN_EMAIL": "bootstrap@example.com",
            "ADMIN_PASSWORD": "Matkhau123",
            "ADMIN_DISPLAY_NAME": "Quản trị khởi tạo",
        }
        with patch.dict(os.environ, environment, clear=False):
            with self.session_factory() as database:
                first = ensure_bootstrap_admin(database)
                second = ensure_bootstrap_admin(database)
                count = database.scalar(
                    select(func.count()).select_from(User).where(User.username == "bootstrap.admin")
                )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None
        self.assertEqual(first.role, "admin")
        self.assertTrue(verify_password("Matkhau123", first.password_hash))
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()

