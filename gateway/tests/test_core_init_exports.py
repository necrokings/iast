"""Ensure core package exports stay stable."""

from __future__ import annotations

import importlib
import sys
import unittest


class _fresh_module:
    def __init__(self, name: str) -> None:
        self.name = name
        self.original = sys.modules.get(name)

    def __enter__(self):
        if self.original is not None:
            sys.modules.pop(self.name, None)
        return importlib.import_module(self.name)

    def __exit__(self, exc_type, exc, tb):
        sys.modules.pop(self.name, None)
        if self.original is not None:
            sys.modules[self.name] = self.original
        return False


class CoreInitTests(unittest.TestCase):
    def test_core_exports(self) -> None:
        with _fresh_module("src.core") as module:
            expected = {
                "get_tn3270_input_channel",
                "get_tn3270_output_channel",
                "TN3270_CONTROL_CHANNEL",
                "Config",
                "ValkeyConfig",
                "TN3270Config",
                "get_config",
                "ErrorCodes",
                "TerminalError",
            }
            self.assertTrue(expected.issubset(set(module.__all__)))
            for name in expected:
                self.assertTrue(hasattr(module, name))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

