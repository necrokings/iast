"""Tests for DynamoDB model helpers."""

from __future__ import annotations

from datetime import datetime
import importlib
import sys
import unittest


class _fresh_module:
    """Context manager to import a module fresh and restore afterwards."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.original = sys.modules.get(name)
        parent_name, _, child = name.rpartition(".")
        self.parent = sys.modules.get(parent_name) if parent_name else None
        self.parent_attr = child or None

    def __enter__(self):
        if self.original is not None:
            sys.modules.pop(self.name, None)
        return importlib.import_module(self.name)

    def __exit__(self, exc_type, exc, tb):
        sys.modules.pop(self.name, None)
        if self.original is not None:
            sys.modules[self.name] = self.original
            if self.parent and self.parent_attr:
                setattr(self.parent, self.parent_attr, self.original)
        else:
            if self.parent and self.parent_attr and hasattr(self.parent, self.parent_attr):
                delattr(self.parent, self.parent_attr)
        return False


class DbModelTests(unittest.TestCase):
    """Round-trip key helpers into DynamoDB friendly payloads."""

    def test_user_to_and_from_dynamodb(self) -> None:
        with _fresh_module("src.db.models") as db_models:
            user = db_models.User(user_id="u1", email="user@example.com")
            item = user.to_dynamodb()
            self.assertEqual(item["PK"], f"{db_models.KeyPrefix.USER}u1")
            restored = db_models.User.from_dynamodb(
                {
                    **item,
                    "updated_at": datetime.now().isoformat(),
                }
            )
            self.assertEqual(restored.email, "user@example.com")

    def test_session_round_trip(self) -> None:
        with _fresh_module("src.db.models") as db_models:
            session = db_models.Session(session_id="s1", user_id="u1")
            item = session.to_dynamodb()
            restored = db_models.Session.from_dynamodb(
                {
                    **item,
                    "last_activity": item["last_activity"],
                }
            )
            self.assertEqual(restored.status, "active")

    def test_ast_execution_round_trip(self) -> None:
        with _fresh_module("src.db.models") as db_models:
            execution = db_models.ASTExecution(
                execution_id="e1",
                session_id="s1",
                ast_name="login",
                status=db_models.ExecutionStatus.RUNNING,
                params={"foo": "bar"},
            )
            item = execution.to_dynamodb()
            self.assertEqual(item["status"], "running")
            restored = db_models.ASTExecution.from_dynamodb(
                {
                    **item,
                    "completed_items": "3",
                    "total_items": "5",
                }
            )
            self.assertEqual(restored.status, db_models.ExecutionStatus.RUNNING)
            self.assertEqual(restored.params["foo"], "bar")

    def test_policy_result_round_trip(self) -> None:
        with _fresh_module("src.db.models") as db_models:
            policy = db_models.PolicyResult(
                execution_id="e1",
                policy_number="123456789",
                status=db_models.PolicyStatus.SUCCESS,
                duration_ms=100,
                data={"k": "v"},
            )
            item = policy.to_dynamodb()
            self.assertEqual(item["status"], "success")
            restored = db_models.PolicyResult.from_dynamodb(
                {
                    **item,
                    "screenshots": ["one"],
                    "data": {"k": "v"},
                }
            )
            self.assertEqual(restored.status, db_models.PolicyStatus.SUCCESS)
            self.assertEqual(restored.data["k"], "v")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
