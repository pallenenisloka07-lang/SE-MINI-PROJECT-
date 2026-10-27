import os
import unittest
import uuid

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "local-test-secret-key-change-before-deployment",
)

from fastapi.testclient import TestClient
from src.main import app


class TestDocumentAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def create_user(self):
        suffix = uuid.uuid4().hex[:12]
        username = f"doc_{suffix}"
        password = "SecurePass123"

        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": password,
            },
        )
        self.assertEqual(
            registration.status_code, 201, registration.text
        )

        login = self.client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": password,
            },
        )
        self.assertEqual(login.status_code, 200, login.text)

        return {
            "Authorization": (
                f"Bearer {login.json()['access_token']}"
            )
        }

    def upload_text(self, headers):
        return self.client.post(
            "/api/documents",
            headers=headers,
            files={
                "file": (
                    "sample.txt",
                    b"AI content management test document.",
                    "text/plain",
                )
            },
            data={"title": "Sample document"},
        )

    def test_upload_and_list_documents(self):
        headers = self.create_user()
        upload = self.upload_text(headers)

        self.assertEqual(upload.status_code, 201, upload.text)
        document_id = upload.json()["id"]

        listing = self.client.get(
            "/api/documents",
            headers=headers,
        )
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertGreaterEqual(listing.json()["total"], 1)

        details = self.client.get(
            f"/api/documents/{document_id}",
            headers=headers,
        )
        self.assertEqual(details.status_code, 200, details.text)
        self.assertEqual(details.json()["title"], "Sample document")

    def test_unsupported_file_is_rejected(self):
        headers = self.create_user()

        response = self.client.post(
            "/api/documents",
            headers=headers,
            files={
                "file": (
                    "malware.exe",
                    b"not an allowed document",
                    "application/octet-stream",
                )
            },
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_document_cannot_be_accessed_by_another_user(self):
        owner_headers = self.create_user()
        other_headers = self.create_user()

        upload = self.upload_text(owner_headers)
        self.assertEqual(upload.status_code, 201, upload.text)
        document_id = upload.json()["id"]

        response = self.client.get(
            f"/api/documents/{document_id}",
            headers=other_headers,
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_edit_document_title(self):
        headers = self.create_user()
        upload = self.upload_text(headers)
        self.assertEqual(upload.status_code, 201, upload.text)
        document_id = upload.json()["id"]

        response = self.client.patch(
            f"/api/documents/{document_id}",
            headers=headers,
            json={"title": "Updated title"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["title"], "Updated title")

    def test_download_and_delete_document(self):
        headers = self.create_user()
        upload = self.upload_text(headers)
        self.assertEqual(upload.status_code, 201, upload.text)
        document_id = upload.json()["id"]

        download = self.client.get(
            f"/api/documents/{document_id}/download",
            headers=headers,
        )
        self.assertEqual(download.status_code, 200, download.text)
        self.assertEqual(
            download.content,
            b"AI content management test document.",
        )

        deletion = self.client.delete(
            f"/api/documents/{document_id}",
            headers=headers,
        )
        self.assertEqual(deletion.status_code, 204, deletion.text)

        details = self.client.get(
            f"/api/documents/{document_id}",
            headers=headers,
        )
        self.assertEqual(details.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)