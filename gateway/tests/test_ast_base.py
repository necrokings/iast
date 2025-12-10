"""Tests for the AST base infrastructure."""

from __future__ import annotations

import threading
import time
import unittest
import unittest.mock

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

    def logoff(self, host: DummyHost):
        return True, "", []

    def process_single_item(self, host: DummyHost, item_id: str, index: int, total: int):
        return True, "", {}

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


class ParallelASTForTesting(AST):
    """AST subclass for testing parallel execution."""

    name = "parallel_test"
    description = "Test AST for parallel execution"

    auth_expected_keywords = ["Welcome"]
    auth_application = "TEST"
    auth_group = "TESTGRP"

    def __init__(self) -> None:
        super().__init__()
        self.processed_items: list = []
        self.should_fail_auth = False
        self.should_fail_process = False
        self.should_fail_logoff = False
        self.process_delay = 0.01  # seconds

    def authenticate(
        self,
        host,
        user: str,
        password: str,
        expected_keywords_after_login: list[str],
        application: str = "",
        group: str = "",
    ):
        if self.should_fail_auth:
            return False, "Auth failed", []
        return True, "", []

    def logoff(self, host, target_screen_keywords=None):
        if self.should_fail_logoff:
            return False, "Logoff failed", []
        return True, "", []

    def process_single_item(self, host, item, index: int, total: int):
        import time

        time.sleep(self.process_delay)
        if self.should_fail_process:
            return False, "Process failed", {}
        self.processed_items.append(item)
        return True, "", {"item": item, "index": index}

    def validate_item(self, item) -> bool:
        return item is not None and item != "INVALID"


class MockAtiInstance:
    """Mock ATI instance for testing."""

    def __init__(self) -> None:
        self.sessions: dict = {}
        self.current_session = ""
        self.variables: dict = {}

    def set(self, name: str, value, xtern: bool = True, verifycert=None):
        name_upper = name.upper()
        if name_upper == "SESSION":
            self.sessions[value] = MockTnz()
            self.current_session = value
            return 0  # Success
        self.variables[name_upper] = value
        return None

    def get_tnz(self, name=None):
        if name is None:
            name = self.current_session
        return self.sessions.get(name)

    def wait(self, timeout):
        pass

    def drop(self, name):
        if name in self.sessions:
            del self.sessions[name]


class MockTnz:
    """Mock Tnz instance for testing."""

    def __init__(self) -> None:
        self.maxrow = 24
        self.maxcol = 80
        self.curadd = 0
        self.pwait = False
        self.updated = False
        self.plane_fa = bytearray(24 * 80)
        self.plane_dc = bytearray(24 * 80)
        self.codec_info = {}

    def scrstr(self, start: int, end: int):
        return " " * (end - start)


class MockDynamoDBClient:
    """Mock DynamoDB client for testing."""

    def put_execution(self, **kwargs):
        pass

    def update_execution(self, **kwargs):
        pass

    def put_policy_result(self, **kwargs):
        pass


class ExecuteParallelTests(unittest.TestCase):
    """Tests for execute_parallel method."""

    def setUp(self) -> None:
        self.ast = ParallelASTForTesting()
        self.host_config = {
            "host": "localhost",
            "port": 3270,
            "secure": False,
            "verifycert": False,
        }
        self.progress_calls: list = []
        self.item_calls: list = []
        self.ast.set_callbacks(
            on_progress=lambda *args: self.progress_calls.append(args),
            on_item_result=lambda *args: self.item_calls.append(args),
        )
        # Patch db client
        self.db_patcher = unittest.mock.patch(
            "src.ast.base.get_dynamodb_client",
            return_value=MockDynamoDBClient(),
        )
        self.db_patcher.start()

    def tearDown(self) -> None:
        self.db_patcher.stop()

    def test_execute_parallel_missing_credentials(self) -> None:
        """Test that missing credentials returns failed result."""
        result = self.ast.execute_parallel(
            self.host_config,
            max_workers=2,
            items=["item1", "item2"],
        )
        self.assertEqual(result.status.value, "failed")
        self.assertIn("username and password", result.error or result.message)

    def test_execute_parallel_no_items(self) -> None:
        """Test that empty items returns success."""
        result = self.ast.execute_parallel(
            self.host_config,
            max_workers=2,
            username="testuser",
            password="testpass",
            items=[],
        )
        self.assertEqual(result.status.value, "success")
        self.assertEqual(result.message, "No items to process")

    def test_execute_parallel_validates_items(self) -> None:
        """Test that invalid items are skipped."""
        with unittest.mock.patch("tnz.ati.Ati", MockAtiInstance):
            with unittest.mock.patch(
                "src.services.tn3270.host.Host.__init__", lambda self, tnz: None
            ):
                result = self.ast.execute_parallel(
                    self.host_config,
                    max_workers=2,
                    username="testuser",
                    password="testpass",
                    items=["valid1", "INVALID", "valid2"],
                )
        # Should have skipped the INVALID item
        skipped = [r for r in result.item_results if r.status == "skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0].item_id, "INVALID")

    def test_execute_parallel_handles_auth_failure(self) -> None:
        """Test that auth failures are properly recorded."""
        self.ast.should_fail_auth = True

        with unittest.mock.patch("tnz.ati.Ati", MockAtiInstance):
            with unittest.mock.patch(
                "src.services.tn3270.host.Host.__init__", lambda self, tnz: None
            ):
                result = self.ast.execute_parallel(
                    self.host_config,
                    max_workers=2,
                    username="testuser",
                    password="testpass",
                    items=["item1"],
                )
        # Should have failed the item due to auth failure
        failed = [r for r in result.item_results if r.status == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertIn("Login failed", failed[0].error or "")

    def test_execute_parallel_handles_process_failure(self) -> None:
        """Test that process failures are properly recorded."""
        self.ast.should_fail_process = True

        with unittest.mock.patch("tnz.ati.Ati", MockAtiInstance):
            with unittest.mock.patch(
                "src.services.tn3270.host.Host.__init__", lambda self, tnz: None
            ):
                result = self.ast.execute_parallel(
                    self.host_config,
                    max_workers=2,
                    username="testuser",
                    password="testpass",
                    items=["item1"],
                )
        failed = [r for r in result.item_results if r.status == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertIn("Process failed", failed[0].error or "")

    def test_execute_parallel_reports_progress(self) -> None:
        """Test that progress is reported for each item."""
        with unittest.mock.patch("tnz.ati.Ati", MockAtiInstance):
            with unittest.mock.patch(
                "src.services.tn3270.host.Host.__init__", lambda self, tnz: None
            ):
                result = self.ast.execute_parallel(
                    self.host_config,
                    max_workers=2,
                    username="testuser",
                    password="testpass",
                    items=["item1", "item2"],
                )
        # Should have progress calls
        self.assertTrue(len(self.progress_calls) >= 2)

    def test_execute_parallel_respects_max_workers(self) -> None:
        """Test that max_workers parameter is included in result data."""
        with unittest.mock.patch("tnz.ati.Ati", MockAtiInstance):
            with unittest.mock.patch(
                "src.services.tn3270.host.Host.__init__", lambda self, tnz: None
            ):
                result = self.ast.execute_parallel(
                    self.host_config,
                    max_workers=5,
                    username="testuser",
                    password="testpass",
                    items=["item1"],
                )
        self.assertEqual(result.data.get("parallelWorkers"), 5)

    def test_execute_parallel_cancellation(self) -> None:
        """Test that cancellation stops processing."""
        # Cancel after a short delay
        def cancel_after_delay():
            import time

            time.sleep(0.02)
            self.ast.cancel()

        cancel_thread = threading.Thread(target=cancel_after_delay)
        cancel_thread.start()

        # Use more items with small delay to test cancellation
        self.ast.process_delay = 0.05
        items = [f"item{i}" for i in range(20)]

        with unittest.mock.patch("tnz.ati.Ati", MockAtiInstance):
            with unittest.mock.patch(
                "src.services.tn3270.host.Host.__init__", lambda self, tnz: None
            ):
                result = self.ast.execute_parallel(
                    self.host_config,
                    max_workers=2,
                    username="testuser",
                    password="testpass",
                    items=items,
                )

        cancel_thread.join()
        self.assertEqual(result.status.value, "cancelled")
        self.assertIn("Cancelled by user", result.message)

    def test_execute_parallel_success(self) -> None:
        """Test successful parallel execution."""
        with unittest.mock.patch("tnz.ati.Ati", MockAtiInstance):
            with unittest.mock.patch(
                "src.services.tn3270.host.Host.__init__", lambda self, tnz: None
            ):
                result = self.ast.execute_parallel(
                    self.host_config,
                    max_workers=2,
                    username="testuser",
                    password="testpass",
                    items=["item1", "item2", "item3"],
                )
        self.assertEqual(result.status.value, "success")
        self.assertEqual(result.data.get("successCount"), 3)
        self.assertEqual(result.data.get("failedCount"), 0)
        self.assertEqual(len(result.item_results), 3)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

