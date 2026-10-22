import os
import unittest
import uuid
from datetime import date

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "local-test-secret-key-change-before-deployment",
)

from fastapi.testclient import TestClient
from src.main import app


class TestSearchAPI(unittest.TestCase):

    def setUp(self):
        self.context = TestClient(app)
        self.client = self.context.__enter__()

        suffix = uuid.uuid4().hex[:12]
        self.username = f"search_{suffix}"
        self.password = "SecurePass123"

        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": self.username,
                "email": f"{self.username}@example.com",
                "password": self.password,
            },
        )
        self.assertEqual(
            registration.status_code, 201, registration.text
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
        self.context.__exit__(None, None, None)

    def upload_sample(self):
        response = self.client.post(
            "/api/documents",
            headers=self.headers,
            data={"title": "Machine Learning Notes"},
            files={
                "file": (
                    "ml_notes.txt",
                    (
                        b"Neural networks are an artificial intelligence "
                        b"technique used in machine learning. They classify "
                        b"images and identify patterns in visual data."
                    ),
                    "text/plain",
                )
            },
        )

        self.assertEqual(response.status_code, 201, response.text)

        document_id = response.json()["id"]

        details = self.client.get(
            f"/api/documents/{document_id}",
            headers=self.headers,
        )

        self.assertEqual(details.status_code, 200, details.text)
        self.assertEqual(
            details.json()["processing_status"],
            "Processed",
            details.text,
        )

        return document_id

    def test_keyword_search_returns_matching_document(self):
        self.upload_sample()

        response = self.client.get(
            "/api/search/keyword",
            params={"q": "neural networks"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200, response.text)

        body = response.json()
        self.assertGreaterEqual(body["total"], 1)
        self.assertGreaterEqual(len(body["items"]), 1)
        self.assertEqual(
            body["items"][0]["title"],
            "Machine Learning Notes",
        )
        self.assertIn("snippet", body["items"][0])

    def test_search_filters_work_together(self):
        document_id = self.upload_sample()

        edit = self.client.patch(
            f"/api/documents/{document_id}",
            headers=self.headers,
            json={"category": "Education"},
        )
        self.assertEqual(edit.status_code, 200, edit.text)

        response = self.client.get(
            "/api/search/keyword",
            params={
                "q": "neural networks",
                "category": "Education",
                "file_type": "txt",
                "date_from": date.today().isoformat(),
                "date_to": date.today().isoformat(),
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200, response.text)

        body = response.json()
        self.assertGreaterEqual(body["total"], 1)

        for item in body["items"]:
            self.assertEqual(item["category"], "Education")
            self.assertEqual(item["file_type"].lower(), "txt")

    def test_semantic_search_returns_relevant_document(self):
        self.upload_sample()

        response = self.client.get(
            "/api/search/semantic",
            params={
                "q": "neural networks artificial intelligence images"
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200, response.text)

        body = response.json()
        self.assertGreaterEqual(body["total"], 1)

        result = body["items"][0]
        self.assertEqual(result["title"], "Machine Learning Notes")
        self.assertIn("relevance_score", result)
        self.assertIn("snippet", result)

    def test_search_does_not_return_another_users_documents(self):
        self.upload_sample()

        suffix = uuid.uuid4().hex[:12]
        username = f"other_{suffix}"

        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "SecurePass123",
            },
        )
        self.assertEqual(
            registration.status_code, 201, registration.text
        )

        login = self.client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": "SecurePass123",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)

        other_headers = {
            "Authorization": (
                f"Bearer {login.json()['access_token']}"
            )
        }

        response = self.client.get(
            "/api/search/keyword",
            params={"q": "neural networks"},
            headers=other_headers,
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)