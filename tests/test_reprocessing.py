
import os
import unittest
import uuid
import asyncio
from unittest.mock import patch

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "local-test-secret-key-change-before-deployment",
)

from fastapi.testclient import TestClient
from jose import jwt

from src.main import app, recover_interrupted_documents
from src.services.vector_store_service import _collection


class TestDocumentReprocessing(unittest.TestCase):

    def test_recovery_resets_and_processes_interrupted_document(self):
        document = {
            "id": 987654,
            "owner_id": 123,
        }

        with patch(
            "src.main.list_processing_documents",
            return_value=[document],
        ), patch(
            "src.main.mark_document_uploaded",
            return_value={"id": 987654},
        ) as mark_uploaded, patch(
            "src.main.process_document",
        ) as process:
            asyncio.run(recover_interrupted_documents())

        mark_uploaded.assert_called_once_with(987654, 123)
        process.assert_called_once_with(987654, 123)

    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

        suffix = uuid.uuid4().hex[:12]
        self.username = f"reprocess_{suffix}"
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

        token = login.json()["access_token"]

        self.headers = {
            "Authorization": f"Bearer {token}"
        }

        claims = jwt.get_unverified_claims(token)
        self.owner_id = str(claims["sub"])

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

    def upload_document(self):
        paragraph = (
            "Artificial intelligence uses machine learning "
            "algorithms to classify information and identify "
            "patterns in data. Neural networks learn useful "
            "representations from training examples. "
            "Document processing extracts text, generates "
            "embeddings, and supports semantic search. "
            "Information retrieval ranks relevant documents "
            "using similarity scores and keyword matching. "
        )

        content = (paragraph * 15).encode("utf-8")

        response = self.client.post(
            "/api/documents",
            headers=self.headers,
            data={"title": "AI Search Test Document"},
            files={
                "file": (
                    "ai_search_test.txt",
                    content,
                    "text/plain",
                )
            },
        )

        self.assertEqual(
            response.status_code,
            201,
            response.text,
        )

        self.document_id = response.json()["id"]
        return self.document_id

    def get_index_count(self):
        result = _collection.get(
            where={
                "$and": [
                    {"owner_id": self.owner_id},
                    {"document_id": str(self.document_id)},
                ]
            },
            include=["metadatas"],
        )

        return len(result["ids"])

    def test_processed_document_has_analysis_and_embeddings(self):
        document_id = self.upload_document()

        response = self.client.get(
            f"/api/documents/{document_id}",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200, response.text)
        document = response.json()

        self.assertEqual(
            document["processing_status"],
            "Processed",
        )
        self.assertGreater(self.get_index_count(), 0)
        self.assertIn("keywords", document)
        self.assertIn("topics", document)
        self.assertLessEqual(len(document["keywords"]), 10)
        self.assertLessEqual(len(document["topics"]), 3)

    def test_reprocessing_does_not_duplicate_vectors(self):
        document_id = self.upload_document()
        before = self.get_index_count()
        self.assertGreater(before, 0)

        response = self.client.post(
            f"/api/documents/{document_id}/reprocess",
            headers=self.headers,
        )

        self.assertEqual(
            response.status_code,
            202,
            response.text,
        )

        details = self.client.get(
            f"/api/documents/{document_id}",
            headers=self.headers,
        )

        self.assertEqual(
            details.status_code,
            200,
            details.text,
        )
        self.assertEqual(
            details.json()["processing_status"],
            "Processed",
        )

        after = self.get_index_count()
        self.assertEqual(
            after,
            before,
            "Reprocessing should not leave duplicate vector entries.",
        )

    def test_interrupted_document_is_found_for_recovery(self):
        from src.repositories.document_repository import (
            mark_document_processing,
            list_processing_documents,
        )

        document_id = self.upload_document()

        updated = mark_document_processing(
            document_id,
            self.owner_id,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["processing_status"], "Processing")

        interrupted = list_processing_documents()
        recovered_candidate_ids = {
            str(document["id"]) for document in interrupted
        }

        self.assertIn(
            str(document_id),
            recovered_candidate_ids,
            "A document left in Processing should be detected at startup.",
        )

    def test_another_user_cannot_reprocess_document(self):
        document_id = self.upload_document()

        other_suffix = uuid.uuid4().hex[:12]
        other_username = f"other_{other_suffix}"

        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": other_username,
                "email": f"{other_username}@example.com",
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
                "username": other_username,
                "password": "SecurePass123",
            },
        )

        self.assertEqual(login.status_code, 200, login.text)

        other_headers = {
            "Authorization": (
                f"Bearer {login.json()['access_token']}"
            )
        }

        response = self.client.post(
            f"/api/documents/{document_id}/reprocess",
            headers=other_headers,
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
