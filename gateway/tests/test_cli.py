"""Tests for the CLI entry points."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src import cli


class CliTests(unittest.TestCase):
    """Ensure CLI helpers orchestrate test execution correctly."""

    def test_internal_run_tests_invokes_unittest(self) -> None:
        fake_suite = object()
        fake_result = MagicMock()
        with patch("src.cli.unittest.TestLoader") as loader_cls, patch(
            "src.cli.unittest.TextTestRunner"
        ) as runner_cls:
            loader = loader_cls.return_value
            runner = runner_cls.return_value
            loader.discover.return_value = fake_suite
            runner.run.return_value = fake_result

            result = cli._run_tests()

        loader_cls.assert_called_once()
        loader.discover.assert_called_once_with(str(cli.TESTS_DIR))
        runner_cls.assert_called_once_with(verbosity=2)
        runner.run.assert_called_once_with(fake_suite)
        self.assertIs(result, fake_result)

    def test_exit_sets_status_code(self) -> None:
        success_result = MagicMock()
        success_result.wasSuccessful.return_value = True
        with self.assertRaises(SystemExit) as ctx_success:
            cli._exit(success_result)
        self.assertEqual(ctx_success.exception.code, 0)

        failure_result = MagicMock()
        failure_result.wasSuccessful.return_value = False
        with self.assertRaises(SystemExit) as ctx_fail:
            cli._exit(failure_result)
        self.assertEqual(ctx_fail.exception.code, 1)

    def test_run_tests_delegates_to_exit(self) -> None:
        fake_result = MagicMock()
        with patch.object(cli, "_run_tests", return_value=fake_result) as run_tests, patch.object(
            cli, "_exit"
        ) as exit_mock:
            cli.run_tests()

        run_tests.assert_called_once()
        exit_mock.assert_called_once_with(fake_result)

    def test_run_coverage_executes_full_flow(self) -> None:
        fake_result = MagicMock()
        fake_cov = MagicMock()

        with patch.object(cli, "_run_tests", return_value=fake_result) as run_tests, patch.object(
            cli, "_exit"
        ) as exit_mock, patch.object(cli, "Coverage", return_value=fake_cov) as cov_cls:
            cli.run_coverage()

        run_tests.assert_called_once()
        cov_cls.assert_called_once_with(source=[str(cli.SRC_DIR)], data_file=str(cli.COVERAGE_FILE))
        fake_cov.erase.assert_called_once()
        fake_cov.start.assert_called_once()
        fake_cov.stop.assert_called_once()
        fake_cov.save.assert_called_once()
        fake_cov.report.assert_called_once()
        fake_cov.html_report.assert_called_once_with(directory=str(cli.HTML_REPORT_DIR))
        exit_mock.assert_called_once_with(fake_result)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

