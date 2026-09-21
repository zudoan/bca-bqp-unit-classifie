from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("CORS_ORIGINS", "https://bca-bqp-frontend.onrender.com")

from api.database import Base, _normalize_database_url, get_database
from api.main import app


class AuthenticationApiTests(unittest.TestCase):
    def test_render_postgres_url_uses_psycopg3_driver(self) -> None:
        self.assertEqual(
            _normalize_database_url("postgresql://user:pass@host/database"),
            "postgresql+psycopg://user:pass@host/database",
        )

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
            with self.session_factory() as database:
                yield database

        app.dependency_overrides[get_database] = override_database
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_bearer_token_supports_cross_domain_session_and_logout(self) -> None:
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Nhóm 3",
                "email": "nhom3@example.com",
                "username": "nhom3",
                "password": "nhom3123",
                "remember": True,
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        token = response.json().get("token")
        self.assertIsInstance(token, str)
        self.assertTrue(token)

        self.client.cookies.clear()
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/api/v1/auth/logout", headers=headers).status_code,
            204,
        )
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=headers).status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
