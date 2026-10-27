"""Dependency-free wiring regression checks for the actual application source.

The lifespan check executes its real function body with mocked initialization
functions; it does NOT substitute for a full FastAPI integration test.
"""

import ast
import asyncio
import unittest
from contextlib import asynccontextmanager
from pathlib import Path


MAIN = Path(__file__).resolve().parent.parent / "src" / "main.py"


class TestAppWiring(unittest.TestCase):
    def test_each_router_is_registered_once(self):
        """Static route audit: ensure duplicate router inclusion cannot recur."""
        parsed = ast.parse(MAIN.read_text())
        routers = [
            call.args[0].id
            for node in ast.walk(parsed)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
            and isinstance(node.args[0], ast.Name)
            for call in [node]
        ]
        self.assertCountEqual(
            routers,
            ["auth_router", "documents_router", "search_router", "admin_router"],
        )

    def test_lifespan_runs_all_database_initialization_once(self):
        """Execute the actual lifespan body with database initialization mocked."""
        parsed = ast.parse(MAIN.read_text())
        lifespan = next(
            node for node in parsed.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
        )
        # Only evaluate the lifespan function, not unavailable app dependencies.
        isolated = ast.Module(body=[lifespan], type_ignores=[])
        ast.fix_missing_locations(isolated)
        calls = []
        initializers = [
            "init_db", "migrate_document_schema", "init_admin_tables",
            "initialize_database",
        ]
        namespace = {"asynccontextmanager": asynccontextmanager, "FastAPI": object}
        for name in initializers:
            namespace[name] = lambda name=name: calls.append(name)
        exec(compile(isolated, str(MAIN), "exec"), namespace)

        async def invoke():
            async with namespace["lifespan"](object()):
                self.assertEqual(calls, initializers)

        asyncio.run(invoke())
        self.assertEqual(calls, initializers)


if __name__ == "__main__":
    unittest.main()
