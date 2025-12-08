"""Ensure tn3270 services package exports expected symbols."""

from __future__ import annotations

import importlib
import sys
import unittest


class _fresh_module:
    """Load a module fresh for coverage and restore the original afterwards."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.original = sys.modules.get(name)
        parent_name, _, child = name.rpartition(".")
        self.parent = sys.modules.get(parent_name) if parent_name else None
        self.parent_attr = child or None

    def __enter__(self):
        if self.original is not None:
            sys.modules.pop(self.name, None)
        self.module = importlib.import_module(self.name)
        return self.module

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


class ServicesTN3270InitTests(unittest.TestCase):
    def test_exports(self) -> None:
        with _fresh_module("src.services.tn3270") as module:
            expected = [
                "Host",
                "ScreenField",
                "ScreenPosition",
                "TN3270Manager",
                "TN3270Session",
                "TN3270Renderer",
                "get_tn3270_manager",
                "init_tn3270_manager",
            ]
            self.assertCountEqual(module.__all__, expected)
            for name in expected:
                self.assertTrue(hasattr(module, name))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
