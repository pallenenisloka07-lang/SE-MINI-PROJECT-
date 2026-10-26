
import os
import unittest
import uuid

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "local-test-secret-key-change-before-deployment",
)

from fastapi.testclient import TestClient

from src.main import app
from src.repositories.admin_repository import list_audit_events


class TestAuditEvents(unittest.TestCase):

    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

        suffix = uuid.uuid4().hex[:12]
        self.username = f"audit_{suffix}"
        self.password = "SecurePass123"
        self.document_id = None

        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": self.username,
                "email": f"{self.username}@example.com",
                "password": self.password,
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
                "username": self.username,
                "password": self.password,
            },
        )

        self.assertEqual(login.status_code, 200, login.text)

        self.headers = {
            "Authorization": (
                f"Bearer {login.json()['access_token']}"
            )
        }

    def tearDown(self):
        if self.document_id is not None:
            try:
                self.client.delete(
                    f"/api/documents/{self.document_id}",
                    headers=self.headers,
                )
            except Exception:
                pass

        self.client_context.__exit__(None, None, None)

    def get_user_events(self):
        result = list_audit_events(offset=0, limit=100)

        return [
            event
            for event in result["items"]
            if event["username"] == self.username
        ]

    def test_successful_login_is_audited(self):
        events = self.get_user_events()

        self.assertTrue(
            any(
                event["action"] == "login_success"
                for event in events
            ),
            "Successful login event was not recorded",
        )

    def test_failed_login_is_audited(self):
        response = self.client.post(
            "/api/auth/login",
            json={
                "username": self.username,
                "password": "IncorrectPassword123",
            },
        )

        self.assertEqual(response.status_code, 401)

        events = self.get_user_events()

        self.assertTrue(
            any(
                event["action"] == "login_failure"
                for event in events
            ),
            "Failed login event was not recorded",
        )

    def test_logout_is_audited(self):
        response = self.client.post(
            "/api/auth/logout",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 204)

        events = self.get_user_events()

        self.assertTrue(
            any(
                event["action"] == "logout"
                for event in events
            ),
            "Logout event was not recorded",
        )

    def test_upload_and_delete_are_audited(self):
        response = self.client.post(
            "/api/documents",
            headers=self.headers,
            data={"title": "Audit Test Document"},
            files={
                "file": (
                    "audit_sample.txt",
                    (
                        b"Artificial intelligence and machine learning "
                        b"support document processing and information "
                        b"retrieval through semantic search."
                    ),
                    "text/plain",
                )
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.document_id = response.json()["id"]

        events = self.get_user_events()

        self.assertTrue(
            any(
                event["action"] == "document_upload"
                for event in events
            ),
            "Document upload event was not recorded",
        )

        delete_response = self.client.delete(
            f"/api/documents/{self.document_id}",
            headers=self.headers,
        )

        self.assertEqual(delete_response.status_code, 204)
        self.document_id = None

        events = self.get_user_events()

        self.assertTrue(
            any(
                event["action"] == "document_delete"
                for event in events
            ),
            "Document deletion event was not recorded",
        )

    def test_audit_entries_include_required_fields(self):
        events = self.get_user_events()

        self.assertTrue(events)

        for event in events:
            self.assertIn("created_at", event)
            self.assertIn("username", event)
            self.assertIn("action", event)
            self.assertIn("details", event)


if __name__ == "__main__":
    unittest.main(verbosity=2)
