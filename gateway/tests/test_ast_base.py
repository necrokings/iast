"""Tests for the AST base infrastructure."""

from __future__ import annotations

import threading
import time
import unittest

from datetime import datetime, timedelta

from src.ast.base import AST, ASTResult, ASTStatus, ItemResult


class DummyHost:
    """Minimal host stub."""


class SampleAST(AST):
    name = "sample"

    def __init__(self) -> None:
        super().__init__()
        self.should_timeout = False
        self.should_fail = False
        self.executed_with: dict | None = None

    def execute(self, host: DummyHost, **kwargs):
        self.executed_with = kwargs
        if kwargs.get("raise_timeout"):
            raise TimeoutError("took too long")
        if kwargs.get("raise_error"):
            raise RuntimeError("boom")

        result = ASTResult(status=ASTStatus.RUNNING, data={"host_type": type(host).__name__})
        self.report_progress(1, 5, current_item="item-1", item_status="running", message="working")
        self.report_item_result("item-1", "success", duration_ms=10)
        return result


class ASTBaseTests(unittest.TestCase):
    """Cover the behavior provided by AST base class."""

    def setUp(self) -> None:
        self.ast = SampleAST()
        self.host = DummyHost()
        self.progress_calls: list = []
        self.item_calls: list = []
        self.pause_calls: list = []
        self.ast.set_callbacks(
            on_progress=lambda *args: self.progress_calls.append(args),
            on_item_result=lambda *args: self.item_calls.append(args),
            on_pause_state=lambda *args: self.pause_calls.append(args),
        )

    def test_pause_resume_and_callbacks(self) -> None:
        self.assertFalse(self.ast.is_paused)
        self.ast.pause()
        self.assertTrue(self.ast.is_paused)
        self.assertTrue(any(call[0] is True for call in self.pause_calls))

        self.ast.resume()
        self.assertFalse(self.ast.is_paused)
        self.assertTrue(any(call[0] is False for call in self.pause_calls))

    def test_cancel_and_wait_if_paused(self) -> None:
        self.ast.pause()

        resume_timer = threading.Timer(0.05, self.ast.resume)
        resume_timer.start()
        self.assertTrue(self.ast.wait_if_paused(timeout=1))

        self.ast.cancel()
        self.assertTrue(self.ast.is_cancelled)
        self.assertFalse(self.ast.wait_if_paused(timeout=0.01))

    def test_run_success_sets_result(self) -> None:
        result = self.ast.run(self.host, execution_id="exec-1")
        self.assertTrue(result.is_success)
        self.assertEqual(result.data["host_type"], "DummyHost")
        self.assertEqual(self.ast.execution_id, "exec-1")
        self.assertTrue(self.progress_calls)
        self.assertTrue(self.item_calls)

    def test_run_handles_timeout(self) -> None:
        result = self.ast.run(self.host, raise_timeout=True)
        self.assertEqual(result.status, ASTStatus.TIMEOUT)
        self.assertIn("Timeout", result.message)

    def test_run_handles_generic_error(self) -> None:
        result = self.ast.run(self.host, raise_error=True)
        self.assertEqual(result.status, ASTStatus.FAILED)
        self.assertIn("Error:", result.message)

    def test_ast_result_helpers_and_item_result(self) -> None:
        start = datetime.now()
        end = start + timedelta(seconds=2)
        result = ASTResult(
            status=ASTStatus.SUCCESS,
            started_at=start,
            completed_at=end,
            item_results=[
                ItemResult(
                    item_id="1",
                    status="success",
                    started_at=start,
                    completed_at=end,
                    duration_ms=10,
                    data={"k": "v"},
                )
            ],
        )

        self.assertAlmostEqual(result.duration, 2, delta=0.1)
        self.assertTrue(result.is_success)
        self.assertEqual(result.item_results[0].data["k"], "v")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

