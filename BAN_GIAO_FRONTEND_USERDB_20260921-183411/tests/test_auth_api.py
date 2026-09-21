from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("CORS_ORIGINS", "https://bca-bqp-frontend.onrender.com/")

from api.database import Base, get_database
from api.main import app
from api.models import User, UserSession
from api.security import verify_password


class AuthenticationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "auth-test.db"
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
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    @staticmethod
    def registration_payload() -> dict[str, object]:
        return {
            "display_name": "Doanh Phạm",
            "email": "doanh@example.com",
            "username": "doanh.pham",
            "password": "Matkhau123",
            "remember": True,
        }

    def test_register_creates_hashed_user_and_authenticated_session(self) -> None:
        response = self.client.post("/api/v1/auth/register", json=self.registration_payload())

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["username"], "doanh.pham")
        cookie = response.headers.get("set-cookie", "")
        self.assertIn("bca_bqp_session=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)

        with Session(self.engine) as database:
            user = database.scalar(select(User).where(User.username == "doanh.pham"))
            sessions = database.scalars(select(UserSession)).all()

        self.assertIsNotNone(user)
        assert user is not None
        self.assertNotEqual(user.password_hash, "Matkhau123")
        self.assertTrue(verify_password("Matkhau123", user.password_hash))
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0].token_hash), 64)

        me_response = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["user"]["email"], "doanh@example.com")

    def test_duplicate_registration_is_rejected(self) -> None:
        first = self.client.post("/api/v1/auth/register", json=self.registration_payload())
        second = self.client.post("/api/v1/auth/register", json=self.registration_payload())

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_login_logout_and_invalid_password(self) -> None:
        self.client.post("/api/v1/auth/register", json=self.registration_payload())
        logout_response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

        invalid_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "doanh.pham", "password": "sai-mat-khau", "remember": False},
        )
        self.assertEqual(invalid_response.status_code, 401)

        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "DOANH.PHAM", "password": "Matkhau123", "remember": False},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)

    def test_registration_validation_rejects_weak_password(self) -> None:
        payload = self.registration_payload()
        payload["password"] = "abcdefgh"

        response = self.client.post("/api/v1/auth/register", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("chữ và một số", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
