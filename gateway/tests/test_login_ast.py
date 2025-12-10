"""Tests for the LoginAST automation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.ast.login import LoginAST
from src.ast.base import ASTStatus


class _FakeHost:
    """Minimal host stub for driving LoginAST."""

    def __init__(self) -> None:
        self.wait_calls: list[str] = []
        self.screens: list[str] = []
        self.filled: list[tuple[str, str]] = []
        self.enter_calls = 0
        self.pf_calls: list[int] = []
        self.typed: list[str] = []

    def wait_for_text(self, text: str, timeout: float = 0) -> bool:
        self.wait_calls.append(text)
        return True

    def show_screen(self, title: str) -> str:
        self.screens.append(title)
        return f"{title}:screen"

    def fill_field_by_label(self, label: str, value: str, case_sensitive: bool = False) -> bool:
        self.filled.append((label, value))
        return True

    def fill_field_at_position(self, row: int, col: int, value: str, clear_first: bool = True) -> None:
        self.filled.append((f"pos:{row},{col}", value))

    def enter(self, text: str | None = None) -> None:
        self.enter_calls += 1

    def pf(self, num: int) -> None:
        self.pf_calls.append(num)

    def type_text(self, text: str) -> None:
        self.typed.append(text)

    def get_formatted_screen(self, show_row_numbers: bool = True) -> str:
        return "formatted-screen"


class _FakeDB:
    def __init__(self) -> None:
        self.executions: list[tuple[dict, dict]] = []
        self.policy_results: list[tuple[str, dict]] = []
        self.updates: list[dict] = []

    def put_execution(self, **kwargs) -> None:
        self.executions.append((kwargs.get("data", {}), kwargs))

    def put_policy_result(self, execution_id: str, policy_number: str, data: dict) -> None:
        self.policy_results.append((policy_number, data))

    def update_execution(self, session_id: str, execution_id: str, updates: dict) -> None:
        self.updates.append(updates)


class LoginASTTests(unittest.TestCase):
    """Coverage for validation and happy-path flows."""

    def test_run_fails_without_credentials(self) -> None:
        host = _FakeHost()
        ast = LoginAST()

        result = ast.run(host)

        self.assertEqual(result.status, ASTStatus.FAILED)
        self.assertIn("username and password", result.message)

    @patch("src.ast.base.get_dynamodb_client")
    @patch("src.ast.login.time.sleep", return_value=None)
    def test_run_processes_valid_policy(self, _sleep: object, mock_db_factory: object) -> None:
        host = _FakeHost()
        fake_db = _FakeDB()
        mock_db_factory.return_value = fake_db

        ast = LoginAST()
        result = ast.run(
            host,
            execution_id="exec-123",
            username="USER1",
            password="PASS1",
            policyNumbers=["ABC123456"],
            userId="app-user",
            sessionId="sess-1",
        )

        self.assertEqual(result.status, ASTStatus.SUCCESS)
        self.assertEqual(len(result.item_results), 1)
        self.assertGreater(len(host.screens), 0)
        self.assertTrue(fake_db.policy_results)
        self.assertTrue(any(u["status"] == "success" for u in fake_db.updates))

    @patch("src.ast.base.get_dynamodb_client")
    @patch("src.ast.login.time.sleep", return_value=None)
    def test_run_skips_invalid_policy(self, _sleep: object, mock_db_factory: object) -> None:
        host = _FakeHost()
        fake_db = _FakeDB()
        mock_db_factory.return_value = fake_db

        ast = LoginAST()
        result = ast.run(
            host,
            execution_id="exec-456",
            username="USER1",
            password="PASS1",
            policyNumbers=["INVALID"],
            userId="app-user",
            sessionId="sess-2",
        )

        self.assertEqual(result.item_results[0].status, "skipped")
        self.assertEqual(fake_db.policy_results[0][0], "INVALID")


if __name__ == "__main__":
    unittest.main()
