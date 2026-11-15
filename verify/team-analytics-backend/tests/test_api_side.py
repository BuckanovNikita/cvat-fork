"""The backend app's API side (what the server process imports to route, check and answer a request) never
imports the calculation code or the worker's jobs, so it cannot query ClickHouse; the calculation code (core/)
imports nothing of Django, so it gets the Technical accounts list as a value. Checked on the sources: importing
them needs a configured Django."""

import ast
import unittest
from pathlib import Path

import cvat.apps.team_analytics as app

APP_DIR = Path(app.__file__).resolve().parent
API_SIDE = ("__init__.py", "apps.py", "default_settings.py", "urls.py", "views.py", "permissions.py", "reads.py",
            "models.py", "serializers.py", "technical_accounts.py")
# Modules that must import nothing of Django: the calculation code, and the rules the suite tests without it.
WITHOUT_DJANGO = ("technical_accounts.py",)
CORE_DIR = APP_DIR / "core"
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

    def test_the_calculation_code_and_the_settings_rules_import_nothing_of_django(self):
        sources = [*sorted(CORE_DIR.rglob("*.py")), *(APP_DIR / name for name in WITHOUT_DJANGO)]
        self.assertGreater(len(sources), 30, "core/ was not found")
        for path in sources:
            for level, module, names in imported(path):
                with self.subTest(module=str(path.relative_to(APP_DIR)), imports=module or names):
                    if level == 0:
                        self.assertNotIn(module.split(".")[0], ("django", "rest_framework", "cvat"))

    def test_the_read_job_is_named_by_its_path_and_exists(self):
        views = (APP_DIR / "views.py").read_text()
        self.assertIn('READ_JOB = "cvat.apps.team_analytics.jobs.read_answer"', views)
        self.assertIn("def read_answer(", (APP_DIR / "jobs.py").read_text())
