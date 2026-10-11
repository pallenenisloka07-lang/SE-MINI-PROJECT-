
import unittest
from pathlib import Path
import tempfile
from document_manager import DocumentManager

ROOT = Path(__file__).resolve().parent.parent


class TestRepositoryStructure(unittest.TestCase):

    def test_readme_exists(self):
        self.assertTrue((ROOT / "README.md").is_file())

    def test_three_project_documents_exist(self):
        documents = list(ROOT.glob("*.docx"))
        self.assertGreaterEqual(
            len(documents),
            3,
            "Expected SRS, SAD, and STP Word documents."
        )
    def test_ci_workflow_exists(self):
        workflow = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow.is_file())

class TestDocumentManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "test.db")
        self.manager = DocumentManager(db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_view_document(self):
        doc_id = self.manager.add("Project Plan", "Project details")
        docs = self.manager.view_all()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["id"], doc_id)
        self.assertEqual(docs[0]["title"], "Project Plan")

    def test_search_by_title(self):
        self.manager.add("AI Research", "Research notes")
        self.manager.add("Meeting Notes", "Team meeting")
        results = self.manager.search("AI")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "AI Research")

    def test_edit_document(self):
        doc_id = self.manager.add("Old Title", "Old content")
        self.assertTrue(
            self.manager.edit(doc_id, "New Title", "New content")
        )
        self.assertEqual(
            self.manager.view_all()[0]["title"], "New Title"
        )

    def test_delete_document(self):
        doc_id = self.manager.add("Temporary", "Temporary content")
        self.assertTrue(self.manager.delete(doc_id))
        self.assertEqual(self.manager.view_all(), [])


if __name__ == "__main__":
    unittest.main()
