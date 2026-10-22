import unittest
import uuid

from fastapi.testclient import TestClient

from src.main import app
from src.api.dependencies import get_current_user
from src.repositories.admin_repository import (
    init_admin_tables,
    record_audit_event,
)


class TestAdminAPI(unittest.TestCase):

    def setUp(self):
        init_admin_tables()

        self.current_user = {
            "sub": "999999",
            "username": "test-admin",
            "role": "admin",
        }

        self.previous_override = app.dependency_overrides.get(
            get_current_user
        )

        app.dependency_overrides[get_current_user] = (
            lambda: self.current_user
        )

        self.client = TestClient(app)

    def tearDown(self):
        if self.previous_override is None:
            app.dependency_overrides.pop(
                get_current_user, None
            )
        else:
            app.dependency_overrides[get_current_user] = (
                self.previous_override
            )

    def test_six_default_categories_exist(self):
        response = self.client.get("/api/admin/categories")

        self.assertEqual(response.status_code, 200, response.text)

        names = {
            item["name"]
            for item in response.json()["items"]
        }

        expected = {
            "Technology",
            "Business and Finance",
            "Education",
            "Health and Medicine",
            "Law and Government",
            "Science and Research",
        }

        self.assertTrue(expected.issubset(names))

    def test_non_admin_cannot_view_categories(self):
        self.current_user["role"] = "user"

        response = self.client.get("/api/admin/categories")

        self.assertEqual(response.status_code, 403)

    def test_non_admin_cannot_view_audit_logs(self):
        self.current_user["role"] = "user"

        response = self.client.get("/api/admin/audit-logs")

        self.assertEqual(response.status_code, 403)

    def test_create_and_delete_category(self):
        name = f"Test Category {uuid.uuid4().hex[:8]}"

        created = self.client.post(
            "/api/admin/categories",
            json={
                "name": name,
                "description": "A temporary category for API testing.",
            },
        )

        self.assertEqual(
            created.status_code, 201, created.text
        )

        category_id = created.json()["id"]

        listing = self.client.get("/api/admin/categories")
        self.assertEqual(listing.status_code, 200)

        listed_names = {
            item["name"]
            for item in listing.json()["items"]
        }

        self.assertIn(name, listed_names)

        deleted = self.client.delete(
            f"/api/admin/categories/{category_id}"
        )

        self.assertEqual(
            deleted.status_code, 200, deleted.text
        )

        self.assertEqual(
            deleted.json()["documents_reset"], 0
        )

    def test_duplicate_category_is_rejected(self):
        name = f"Duplicate Test {uuid.uuid4().hex[:8]}"

        payload = {
            "name": name,
            "description": "Testing duplicate category handling.",
        }

        first = self.client.post(
            "/api/admin/categories",
            json=payload,
        )

        self.assertEqual(first.status_code, 201, first.text)

        second = self.client.post(
            "/api/admin/categories",
            json=payload,
        )

        self.assertEqual(second.status_code, 409, second.text)

        self.client.delete(
            f"/api/admin/categories/{first.json()['id']}"
        )

    def test_audit_log_pagination(self):
        for index in range(12):
            record_audit_event(
                user_id=999999,
                username="test-admin",
                action="test_audit_event",
                details=f"Test event {uuid.uuid4().hex}",
            )

        first = self.client.get(
            "/api/admin/audit-logs?page=1"
        )

        self.assertEqual(first.status_code, 200, first.text)

        first_data = first.json()

        self.assertEqual(first_data["limit"], 10)
        self.assertEqual(len(first_data["items"]), 10)
        self.assertGreaterEqual(first_data["total"], 12)

        second = self.client.get(
            "/api/admin/audit-logs?page=2"
        )

        self.assertEqual(second.status_code, 200, second.text)

        second_data = second.json()

        self.assertTrue(second_data["items"])

        first_ids = {
            item["id"]
            for item in first_data["items"]
        }

        second_ids = {
            item["id"]
            for item in second_data["items"]
        }

        self.assertTrue(first_ids.isdisjoint(second_ids))

        for item in first_data["items"]:
            self.assertIn("created_at", item)
            self.assertIn("action", item)
            self.assertIn("username", item)


if __name__ == "__main__":
    unittest.main(verbosity=2)