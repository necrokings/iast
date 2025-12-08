"""Ensure services package exports expected helpers."""

from __future__ import annotations

import importlib
import unittest


class ServicesInitTests(unittest.TestCase):
    """Simple smoke tests for package exports."""

    def test_services_exports(self) -> None:
        services_module = importlib.import_module("src.services")
        services_module = importlib.reload(services_module)

        expected_exports = [
            "ValkeyClient",
            "get_valkey_client",
            "init_valkey_client",
            "close_valkey_client",
            "TN3270Manager",
            "TN3270Session",
            "TN3270Renderer",
            "get_tn3270_manager",
            "init_tn3270_manager",
        ]

        self.assertCountEqual(services_module.__all__, expected_exports)
        for name in expected_exports:
            self.assertTrue(hasattr(services_module, name))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
