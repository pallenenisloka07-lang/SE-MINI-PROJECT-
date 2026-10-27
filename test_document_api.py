import os
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ["JWT_SECRET_KEY"] = "test-only-secret-for-document-api-tests"

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from backend.app.database.connection import Base, get_db
from backend.app.models.models import User, Category, Document
from backend.app.storage.file_storage import STORAGE_DIR


class DocumentApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.TestSession = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )

        def override_get_db():
            db = self.TestSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.owner = User(
            username="owner-a",
            email="owner-a@example.com",
            password_hash="external-auth",
            role="user",
        )
        self.category = Category(name="API Test Category", description="Temporary API test category")
        with self.TestSession() as db:
            db.add_all([self.owner, self.category])
            db.commit()
            db.refresh(self.owner)
            db.refresh(self.category)
            self.owner_id = self.owner.id
            self.category_id = self.category.id

        self.storage_name = f"api-test-{uuid4().hex}.txt"
        self.storage_path = STORAGE_DIR / self.storage_name
        self.storage_path.write_text("isolated test document", encoding="utf-8")

        with self.TestSession() as db:
            document = Document(
                owner_id=self.owner_id,
                category_id=self.category_id,
                title="Original title",
                original_filename="original.txt",
                file_type="txt",
                file_size=22,
                storage_path=str(Path("storage") / self.storage_name),
                status="Processed",
                extracted_text="isolated test document",
                category_score=1.0,
                category_source="auto",
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            self.document_id = document.id

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        if self.storage_path.exists():
            self.storage_path.unlink()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def make_token(self, user_id, username):
        from datetime import datetime, timedelta, timezone
        from uuid import uuid4

        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": str(user_id),
                "username": username,
                "role": "user",
                "jti": uuid4().hex,
                "iat": now,
                "exp": now + timedelta(minutes=30),
            },
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )

    def headers(self, user_id, username):
        return {
            "Authorization": f"Bearer {self.make_token(user_id, username)}"
        }

    def mock_auth_user(self, user_id, username, email):
        auth_user = type(
            "AuthUser",
            (),
            {"id": user_id, "username": username, "email": email},
        )()
        return patch(
            "backend.app.api_documents.find_user_by_username",
            return_value=auth_user,
        )

    def test_update_without_token_is_rejected(self):
        response = self.client.patch(
            f"/api/documents/{self.document_id}",
            json={"title": "Changed"},
        )
        self.assertEqual(response.status_code, 401)

    def test_delete_without_token_is_rejected(self):
        response = self.client.delete(f"/api/documents/{self.document_id}")
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_is_rejected(self):
        response = self.client.patch(
            f"/api/documents/{self.document_id}",
            headers={"Authorization": "Bearer invalid-token"},
            json={"title": "Changed"},
        )
        self.assertEqual(response.status_code, 401)

    def test_empty_update_is_rejected_after_authentication(self):
        with self.mock_auth_user(101, "owner-a", "owner-a@example.com"):
            response = self.client.patch(
                f"/api/documents/{self.document_id}",
                headers=self.headers(101, "owner-a"),
                json={},
            )
        self.assertEqual(response.status_code, 200)

    def test_owner_can_update_document(self):
        with self.mock_auth_user(101, "owner-a", "owner-a@example.com"):
            response = self.client.patch(
                f"/api/documents/{self.document_id}",
                headers=self.headers(101, "owner-a"),
                json={"title": "Updated by owner"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["title"], "Updated by owner")

        with self.TestSession() as db:
            saved = db.get(Document, self.document_id)
            self.assertEqual(saved.title, "Updated by owner")

    def test_other_user_cannot_update_document(self):
        with self.mock_auth_user(202, "owner-b", "owner-b@example.com"):
            response = self.client.patch(
                f"/api/documents/{self.document_id}",
                headers=self.headers(202, "owner-b"),
                json={"title": "Unauthorized change"},
            )
        self.assertEqual(response.status_code, 404)

        with self.TestSession() as db:
            saved = db.get(Document, self.document_id)
            self.assertEqual(saved.title, "Original title")

    def test_owner_can_delete_document_and_file(self):
        with self.mock_auth_user(101, "owner-a", "owner-a@example.com"):
            response = self.client.delete(
                f"/api/documents/{self.document_id}",
                headers=self.headers(101, "owner-a"),
            )
        self.assertEqual(response.status_code, 204, response.text)
        self.assertFalse(self.storage_path.exists())

        with self.TestSession() as db:
            self.assertIsNone(db.get(Document, self.document_id))

    def test_other_user_cannot_delete_document(self):
        with self.mock_auth_user(202, "owner-b", "owner-b@example.com"):
            response = self.client.delete(
                f"/api/documents/{self.document_id}",
                headers=self.headers(202, "owner-b"),
            )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.storage_path.exists())

        with self.TestSession() as db:
            self.assertIsNotNone(db.get(Document, self.document_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)
