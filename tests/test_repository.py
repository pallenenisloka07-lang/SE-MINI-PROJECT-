import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestRepositoryStructure(unittest.TestCase):

    def test_readme_exists(self):
        self.assertTrue((ROOT / "README.md").is_file())

    def test_ci_workflow_exists(self):
        workflow = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow.is_file())


if __name__ == "__main__":
    unittest.main()
