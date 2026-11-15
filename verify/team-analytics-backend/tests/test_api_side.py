"""The backend app's API side (what the server process imports to route, check and answer a request) never
imports the calculation code or the worker's jobs, so it cannot query ClickHouse. Checked on the sources:
importing them needs a configured Django."""

import ast
import unittest
from pathlib import Path

import cvat.apps.team_analytics as app

APP_DIR = Path(app.__file__).resolve().parent
API_SIDE = ("__init__.py", "apps.py", "default_settings.py", "urls.py", "views.py", "permissions.py", "reads.py")
FORBIDDEN_PACKAGES = ("clickhouse_connect",)
FORBIDDEN_APP_MODULES = ("core", "jobs")


def imported(path: Path) -> list[tuple[int, str, list[str]]]:
    """(relative level, module, names) of every import in a source file, wherever it stands."""
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found += [(0, alias.name, []) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((node.level, node.module or "", [alias.name for alias in node.names]))
    return found


class ApiSideTest(unittest.TestCase):
    def test_every_api_side_module_exists(self):
        for name in API_SIDE:
            self.assertTrue((APP_DIR / name).is_file(), name)
        modules = {path.name for path in APP_DIR.glob("*.py")}
        self.assertEqual(modules - set(API_SIDE), {"jobs.py"}, "a new module must be put on one side or the other")

    def test_the_api_side_imports_neither_the_calculation_code_nor_clickhouse(self):
        for name in API_SIDE:
            for level, module, names in imported(APP_DIR / name):
                with self.subTest(module=name, imports=module or names):
                    top = module.split(".")[0]
                    self.assertNotIn(top, FORBIDDEN_PACKAGES)
                    if level == 1:  # from . import x / from .x import y
                        reached = {top} if module else set(names)
                        self.assertFalse(reached & set(FORBIDDEN_APP_MODULES), reached)
                    if module.startswith("cvat.apps.team_analytics"):
                        rest = module.removeprefix("cvat.apps.team_analytics").lstrip(".").split(".")[0]
                        reached = {rest} if rest else set(names)
                        self.assertFalse(reached & set(FORBIDDEN_APP_MODULES), reached)

    def test_the_read_job_is_named_by_its_path_and_exists(self):
        views = (APP_DIR / "views.py").read_text()
        self.assertIn('READ_JOB = "cvat.apps.team_analytics.jobs.read_answer"', views)
        self.assertIn("def read_answer(", (APP_DIR / "jobs.py").read_text())
