import unittest
import uuid

from fastapi.testclient import TestClient
from src.main import app


class TestRegistration(unittest.TestCase):

    def unique_payload(self, password="SecurePass123"):
        unique = uuid.uuid4().hex[:12]
        return {
            "username": f"test_{unique}",
            "email": f"test_{unique}@example.com",
            "password": password,
        }

    def test_valid_registration(self):
        payload = self.unique_payload()

        # Entering the context runs FastAPI startup handlers.
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/register",
                json=payload,
            )

        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()
        self.assertEqual(data["username"], payload["username"])
        self.assertEqual(data["role"], "User")
        self.assertNotIn("password", data)
        self.assertNotIn("password_hash", data)

    def test_duplicate_registration(self):
        payload = self.unique_payload()

        with TestClient(app) as client:
            first = client.post("/api/auth/register", json=payload)
            second = client.post("/api/auth/register", json=payload)

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 409, second.text)

    def test_weak_password(self):
        payload = self.unique_payload(password="weak")

        with TestClient(app) as client:
            response = client.post(
                "/api/auth/register",
                json=payload,
            )

        self.assertEqual(response.status_code, 400, response.text)


if __name__ == "__main__":
    unittest.main()