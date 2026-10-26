import os
import tempfile
from pathlib import Path

_TEST_DIR = tempfile.TemporaryDirectory(prefix="ai_cms_documents_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TEST_DIR.name) / 'users.db'}"
os.environ["AI_CMS_DATABASE_URL"] = f"sqlite:///{Path(_TEST_DIR.name) / 'documents.db'}"
os.environ["JWT_SECRET_KEY"] = "integration-test-secret-only"

from fastapi.testclient import TestClient
from src.main import app
from src.repositories.user_repository import init_db
from backend.app.database.init_db import initialize_database

init_db()
initialize_database()
client = TestClient(app)


def get_token():
    username = "document_test_user"
    password = "TestPassword123!"
    email = "document_test_user@example.com"

    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code in (201, 400, 409), response.text

    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_document_lifecycle():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Upload
    response = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("integration.txt", b"Integration test content", "text/plain")},
        data={"title": "Integration document"},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    doc_id = document["id"]
    assert document["title"] == "Integration document"

    # List
    response = client.get("/api/documents", headers=headers)
    assert response.status_code == 200, response.text
    assert any(item["id"] == doc_id for item in response.json()["items"])

    # Details
    response = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == doc_id

    # Download
    response = client.get(f"/api/documents/{doc_id}/download", headers=headers)
    assert response.status_code == 200, response.text
    assert response.content == b"Integration test content"

    # Edit title
    response = client.patch(
        f"/api/documents/{doc_id}",
        headers=headers,
        json={"title": "Updated integration document"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated integration document"

    # Delete
    response = client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert response.status_code == 204, response.text

    # Deleted document is no longer accessible
    response = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert response.status_code == 404, response.text


def test_document_endpoints_require_authentication():
    response = client.get("/api/documents")
    assert response.status_code == 401, response.text


def test_unsupported_file_type_is_rejected():
    token = get_token()
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malware.exe", b"not allowed", "application/octet-stream")},
    )
    assert response.status_code == 400, response.text
