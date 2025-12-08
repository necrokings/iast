"""CLI helpers exposed via `uv run` entry points."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Sequence

import pytest
from coverage import Coverage


PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
TESTS_DIR: Final = PROJECT_ROOT / "tests"
SRC_DIR: Final = PROJECT_ROOT / "src"
COVERAGE_FILE: Final = PROJECT_ROOT / ".coverage"
HTML_REPORT_DIR: Final = PROJECT_ROOT / "htmlcov"


def _run_pytest(extra_args: Sequence[str] | None = None) -> int:
    """Invoke pytest for the gateway test suite."""

    args = [str(TESTS_DIR)]
    if extra_args:
        args.extend(extra_args)
    return pytest.main(args)


def _exit(exit_code: int) -> None:
    raise SystemExit(exit_code)


def run_tests() -> None:
    """Execute the test suite with pytest."""

    _exit(_run_pytest())


def run_coverage() -> None:
    """Execute the suite while collecting coverage data."""

    cov = Coverage(source=[str(SRC_DIR)], data_file=str(COVERAGE_FILE))
    cov.erase()
    cov.start()
    exit_code = _run_pytest()
    cov.stop()
    cov.save()
    cov.report(skip_covered=True, skip_empty=True, show_missing=True)
    cov.html_report(directory=str(HTML_REPORT_DIR))
    _exit(exit_code)
