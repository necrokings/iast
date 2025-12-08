"""CLI helpers exposed via `uv run` entry points."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Final

from coverage import Coverage


PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
TESTS_DIR: Final = PROJECT_ROOT / "tests"
SRC_DIR: Final = PROJECT_ROOT / "src"
COVERAGE_FILE: Final = PROJECT_ROOT / ".coverage"
HTML_REPORT_DIR: Final = PROJECT_ROOT / "htmlcov"


def _run_tests() -> unittest.result.TestResult:
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_DIR))
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


def _exit(result: unittest.result.TestResult) -> None:
    raise SystemExit(0 if result.wasSuccessful() else 1)


def run_tests() -> None:
    """Execute the unittest suite."""
    _exit(_run_tests())


def run_coverage() -> None:
    """Execute the suite while collecting coverage data."""

    cov = Coverage(source=[str(SRC_DIR)], data_file=str(COVERAGE_FILE))
    cov.erase()
    cov.start()
    result = _run_tests()
    cov.stop()
    cov.save()
    cov.report(skip_covered=True, skip_empty=True, show_missing=True)
    cov.html_report(directory=str(HTML_REPORT_DIR))
    _exit(result)
