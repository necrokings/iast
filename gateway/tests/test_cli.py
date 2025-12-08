"""Tests for the CLI entry points."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src import cli


def test_internal_run_pytest_invokes_pytest_main() -> None:
    with patch("src.cli.pytest.main", return_value=0) as main:
        exit_code = cli._run_pytest(["-k", "subset"])

    main.assert_called_once_with([str(cli.TESTS_DIR), "-k", "subset"])
    assert exit_code == 0


def test_exit_sets_status_code() -> None:
    with pytest.raises(SystemExit) as ctx_success:
        cli._exit(0)
    assert ctx_success.value.code == 0

    with pytest.raises(SystemExit) as ctx_fail:
        cli._exit(5)
    assert ctx_fail.value.code == 5


def test_run_tests_delegates_to_exit() -> None:
    with patch.object(cli, "_run_pytest", return_value=3) as run_pytest, patch.object(
        cli, "_exit"
    ) as exit_mock:
        cli.run_tests()

    run_pytest.assert_called_once_with()
    exit_mock.assert_called_once_with(3)


def test_run_coverage_executes_full_flow() -> None:
    fake_cov = MagicMock()

    with patch.object(cli, "_run_pytest", return_value=0) as run_pytest, patch.object(
        cli, "_exit"
    ) as exit_mock, patch("src.cli.Coverage", return_value=fake_cov) as cov_cls:
        cli.run_coverage()

    run_pytest.assert_called_once_with()
    cov_cls.assert_called_once_with(source=[str(cli.SRC_DIR)], data_file=str(cli.COVERAGE_FILE))
    fake_cov.erase.assert_called_once()
    fake_cov.start.assert_called_once()
    fake_cov.stop.assert_called_once()
    fake_cov.save.assert_called_once()
    fake_cov.report.assert_called_once_with(skip_covered=True, skip_empty=True, show_missing=True)
    fake_cov.html_report.assert_called_once_with(directory=str(cli.HTML_REPORT_DIR))
    exit_mock.assert_called_once_with(0)

