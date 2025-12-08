"""Ensure top-level package exports remain available."""

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


class PackageInitTests(unittest.TestCase):
    def test_gateway_package_exports(self) -> None:
        with _fresh_module("src") as module:
            for name in [
                "main",
                "Config",
                "TN3270Manager",
                "ValkeyClient",
                "create_data_message",
            ]:
                self.assertTrue(hasattr(module, name))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

