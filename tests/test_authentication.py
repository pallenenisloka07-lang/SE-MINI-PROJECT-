"""AI-CMS authentication API tests for Sloka's current implementation.

Covers the currently implemented registration/login behavior and password
storage. Uses a temporary SQLite database, not the normal users.db.

Copy this file into tests/test_auth.py (replacing the current file) and run:
    python -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

# user_repository.py reads DATABASE_URL when imported, so set it first.
_TEST_DB_DIR = tempfile.TemporaryDirectory(prefix="ai_cms_auth_tests_")
_TEST_DB_PATH = Path(_TEST_DB_DIR.name) / "users_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-do-not-use-in-production"

from fastapi.testclient import TestClient  # noqa: E402
from src.main import app  # noqa: E402
from src.repositories.user_repository import SessionLocal, User  # noqa: E402


class TestAuthenticationAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Startup initializes the temporary database.
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        _TEST_DB_DIR.cleanup()

    def unique_payload(self, password="SecurePass123"):
        suffix = uuid.uuid4().hex[:12]
        return {
            "username": f"qa_{suffix}",
            "email": f"qa_{suffix}@example.com",
            "password": password,
        }

    def register(self, payload):
        return self.client.post("/api/auth/register", json=payload)

    def login(self, username, password):
        return self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )

    # STP TC-Auth-01 / FR-001
    def test_auth_01_valid_registration_creates_user_role(self):
        payload = self.unique_payload()
        response = self.register(payload)

        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["username"], payload["username"])
        self.assertEqual(body["role"], "User")
        self.assertIn("id", body)
        self.assertNotIn("password", body)
        self.assertNotIn("password_hash", body)

    # STP TC-Auth-02 / FR-001
    def test_auth_02_duplicate_username_is_rejected(self):
        payload = self.unique_payload()
        first = self.register(payload)
        second = self.register(payload)

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 409, second.text)

    # STP TC-Auth-02 / FR-001
    def test_auth_02_duplicate_email_is_rejected(self):
        first_payload = self.unique_payload()
        first = self.register(first_payload)
        self.assertEqual(first.status_code, 201, first.text)

        second_payload = self.unique_payload()
        second_payload["email"] = first_payload["email"]
        second = self.register(second_payload)
        self.assertEqual(second.status_code, 409, second.text)

    # STP TC-Auth-02 / FR-001
    def test_auth_02_invalid_email_is_rejected(self):
        payload = self.unique_payload()
        payload["email"] = "not-an-email"
        response = self.register(payload)

        # auth.py uses Pydantic EmailStr, so request validation should reject it.
        self.assertEqual(response.status_code, 422, response.text)

    # STP TC-Auth-02 / FR-001
    def test_auth_02_short_or_weak_password_is_rejected(self):
        payload = self.unique_payload(password="weak")
        response = self.register(payload)
        self.assertEqual(response.status_code, 400, response.text)

    # STP TC-Auth-02 / FR-001
    def test_auth_02_password_without_digit_is_rejected(self):
        payload = self.unique_payload(password="SecurePassword")
        response = self.register(payload)
        self.assertEqual(response.status_code, 400, response.text)

    # STP TC-Auth-01 / SR-002
    def test_sec_02_password_is_hashed_in_database(self):
        payload = self.unique_payload()
        response = self.register(payload)
        self.assertEqual(response.status_code, 201, response.text)

        with SessionLocal() as db:
            user = db.query(User).filter(
                User.username == payload["username"]
            ).first()
            self.assertIsNotNone(user)
            self.assertNotEqual(user.password_hash, payload["password"])
            self.assertTrue(
                user.password_hash.startswith("$2"),
                "Expected a bcrypt hash in the database",
            )

    # STP TC-Auth-03 / FR-002
    def test_auth_03_valid_login_returns_access_token(self):
        payload = self.unique_payload()
        registration = self.register(payload)
        self.assertEqual(registration.status_code, 201, registration.text)

        response = self.login(payload["username"], payload["password"])
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body.get("access_token"))
        self.assertEqual(body.get("token_type"), "bearer")

        # SAD API contract specifies these additional response fields.
        # Current auth_service.py does not appear to return them yet.
        self.assertIn(
            "expires_in",
            body,
            "SAD contract mismatch: login response should include expires_in",
        )
        self.assertIn(
            "role",
            body,
            "SAD contract mismatch: login response should include role",
        )

    # STP TC-Auth-04 / FR-002
    def test_auth_04_wrong_password_is_rejected(self):
        payload = self.unique_payload()
        registration = self.register(payload)
        self.assertEqual(registration.status_code, 201, registration.text)

        response = self.login(payload["username"], "WrongPassword123")
        self.assertEqual(response.status_code, 401, response.text)

    # STP TC-Auth-04 / FR-002
    def test_auth_04_unknown_username_is_rejected(self):
        response = self.login(
            f"missing_{uuid.uuid4().hex[:12]}",
            "SecurePass123",
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_health_endpoint_is_available(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "healthy")


if __name__ == "__main__":
    unittest.main(verbosity=2)
