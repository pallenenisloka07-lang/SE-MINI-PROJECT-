import os
import unittest
import uuid

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-for-logout-tests-change-before-deployment",
)

from fastapi.testclient import TestClient
from src.main import app
from src.services.auth_service import decode_access_token


class TestLogoutAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def create_access_token(self):
        unique = uuid.uuid4().hex[:12]
        username = f"logout_{unique}"

        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "SecurePass123",
            },
        )

        self.assertEqual(
            registration.status_code,
            201,
            registration.text,
        )

        login = self.client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": "SecurePass123",
            },
        )

        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def test_logout_revokes_token_immediately(self):
        token = self.create_access_token()

        # The token should work before logout.
        self.assertTrue(decode_access_token(token)["sub"])

        response = self.client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 204)

        # The same token must fail immediately after logout.
        with self.assertRaises(PermissionError):
            decode_access_token(token)

        # Reusing the token for logout must also be rejected.
        repeated = self.client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(repeated.status_code, 401)

    def test_logout_without_token_is_rejected(self):
        response = self.client.post("/api/auth/logout")
        self.assertEqual(response.status_code, 401)

    def test_logout_with_invalid_token_is_rejected(self):
        response = self.client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid-token"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)