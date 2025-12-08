"""Tests for AST factory helpers."""

from __future__ import annotations

import importlib
import unittest

import src.models.ast as ast_module


class ASTFactoryTests(unittest.TestCase):
    """Ensure AST helper constructors populate metadata correctly."""

    @classmethod
    def setUpClass(cls) -> None:
        importlib.reload(ast_module)

    def test_create_ast_status_message_sets_meta(self) -> None:
        msg = ast_module.create_ast_status_message(
            session_id="sess",
            ast_name="login",
            status="running",
            message="Starting",
            error=None,
            duration=1.5,
            data={"k": "v"},
        )
        self.assertIsInstance(msg, ast_module.ASTStatusMessage)
        self.assertEqual(msg.meta.status, "running")
        self.assertEqual(msg.meta.ast_name, "login")
        self.assertEqual(msg.payload, "Starting")

    def test_create_ast_progress_message_calculates_percent(self) -> None:
        msg = ast_module.create_ast_progress_message(
            session_id="sess",
            execution_id="exec",
            ast_name="login",
            current=2,
            total=4,
            current_item="item-2",
            item_status="running",
            message="Halfway",
        )
        self.assertIsInstance(msg, ast_module.ASTProgressMessage)
        self.assertEqual(msg.meta.percent, 50)
        self.assertEqual(msg.meta.current_item, "item-2")
        self.assertEqual(msg.meta.item_status, "running")

    def test_create_ast_item_result_message_sets_payload(self) -> None:
        msg = ast_module.create_ast_item_result_message(
            session_id="sess",
            execution_id="exec",
            item_id="item-1",
            status="success",
            duration_ms=42,
            error=None,
            data={"detail": True},
        )
        self.assertIsInstance(msg, ast_module.ASTItemResultMessage)
        self.assertEqual(msg.payload, "item-1")
        self.assertEqual(msg.meta.duration_ms, 42)
        self.assertEqual(msg.meta.status, "success")

    def test_create_ast_paused_message_uses_payload(self) -> None:
        msg = ast_module.create_ast_paused_message(
            "sess", paused=True, message="Paused for review"
        )
        self.assertIsInstance(msg, ast_module.ASTPausedMessage)
        self.assertTrue(msg.meta.paused)
        self.assertEqual(msg.payload, "Paused for review")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

