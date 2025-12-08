"""Ensure module-level initialization code executes under coverage."""

from __future__ import annotations

import importlib
import sys
import unittest
from unittest.mock import patch


class _fresh_module:
    def __init__(self, name: str) -> None:
        self.name = name
        self.original = sys.modules.get(name)

    def __enter__(self):
        if self.original is not None:
            sys.modules.pop(self.name, None)
        return importlib.import_module(self.name)

    def __exit__(self, exc_type, exc, tb):
        sys.modules.pop(self.name, None)
        if self.original is not None:
            sys.modules[self.name] = self.original
        return False


class ModuleImportTests(unittest.TestCase):
    def test_app_module_configures_structlog(self) -> None:
        with patch("structlog.configure") as mock_config, patch(
            "structlog.get_logger", return_value=object()
        ):
            with _fresh_module("src.app") as app_module:
                self.assertTrue(mock_config.called)
                self.assertTrue(hasattr(app_module, "shutdown"))

    def test_cli_module_sets_paths(self) -> None:
        with _fresh_module("src.cli") as cli_module:
            self.assertTrue(cli_module.PROJECT_ROOT.exists())
            self.assertTrue(cli_module.TESTS_DIR.name, "tests")

    def test_db_init_exports(self) -> None:
        with _fresh_module("src.db") as db_module:
            expected = {
                "get_dynamodb_client",
                "DynamoDBClient",
                "User",
                "Session",
                "ASTExecution",
                "PolicyResult",
                "ExecutionStatus",
            }
            self.assertTrue(expected.issubset(set(db_module.__all__)))

    def test_ast_init_exports(self) -> None:
        with _fresh_module("src.ast") as ast_module:
            for name in ("LoginAST", "ASTStatus"):
                self.assertTrue(hasattr(ast_module, name))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

