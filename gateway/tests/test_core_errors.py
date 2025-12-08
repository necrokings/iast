"""Tests for src.core.errors."""

from __future__ import annotations

import importlib
import unittest

from src.core import errors as errors_module


class TerminalErrorTests(unittest.TestCase):
    """Ensure TerminalError retains metadata."""

    @classmethod
    def setUpClass(cls) -> None:
        importlib.reload(errors_module)

    def test_terminal_error_from_enum(self) -> None:
        err = errors_module.TerminalError(
            errors_module.ErrorCodes.AUTH_REQUIRED, "login required"
        )

        self.assertEqual(err.code, errors_module.ErrorCodes.AUTH_REQUIRED.value)
        self.assertEqual(err.message, "login required")
        self.assertEqual(
            err.to_dict(),
            {"code": "E1001", "message": "login required"},
        )
        self.assertEqual(
            repr(err),
            "TerminalError('E1001', 'login required')",
        )

    def test_terminal_error_accepts_raw_code(self) -> None:
        err = errors_module.TerminalError("E5999", "custom failure")

        self.assertEqual(err.code, "E5999")
        self.assertEqual(err.message, "custom failure")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

