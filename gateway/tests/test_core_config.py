"""Tests for src.core.config."""

from __future__ import annotations

import importlib
import os
import unittest
from unittest.mock import patch

from src.core import config as config_module


class ConfigTests(unittest.TestCase):
    """Exercise environment-driven configuration helpers."""

    def tearDown(self) -> None:  # pragma: no cover - helper
        config_module._config = None

    @patch.dict(
        os.environ,
        {
            "DYNAMODB_ENDPOINT": "https://dynamodb.local",
            "AWS_REGION": "eu-central-1",
            "DYNAMODB_TABLE": "custom-terminal",
            "AWS_ACCESS_KEY_ID": "key123",
            "AWS_SECRET_ACCESS_KEY": "secret123",
            "VALKEY_HOST": "valkey.local",
            "VALKEY_PORT": "6390",
            "VALKEY_DB": "2",
            "VALKEY_PASSWORD": "p455",
            "TN3270_HOST": "mainframe.local",
            "TN3270_PORT": "2323",
            "TN3270_COLS": "132",
            "TN3270_ROWS": "27",
            "TN3270_TERMINAL_TYPE": "IBM-3278-2-E",
            "TN3270_MAX_SESSIONS": "5",
            "TN3270_SECURE": "TRUE",
        },
        clear=False,
    )
    def test_get_config_reads_environment(self) -> None:
        importlib.reload(config_module)
        config_module._config = None

        cfg = config_module.get_config()

        self.assertEqual(cfg.dynamodb.endpoint, "https://dynamodb.local")
        self.assertEqual(cfg.dynamodb.region, "eu-central-1")
        self.assertEqual(cfg.dynamodb.table_name, "custom-terminal")
        self.assertEqual(cfg.dynamodb.access_key_id, "key123")
        self.assertEqual(cfg.dynamodb.secret_access_key, "secret123")

        self.assertEqual(cfg.valkey.host, "valkey.local")
        self.assertEqual(cfg.valkey.port, 6390)
        self.assertEqual(cfg.valkey.db, 2)
        self.assertEqual(cfg.valkey.password, "p455")

        self.assertEqual(cfg.tn3270.host, "mainframe.local")
        self.assertEqual(cfg.tn3270.port, 2323)
        self.assertEqual(cfg.tn3270.cols, 132)
        self.assertEqual(cfg.tn3270.rows, 27)
        self.assertEqual(cfg.tn3270.terminal_type, "IBM-3278-2-E")
        self.assertEqual(cfg.tn3270.max_sessions, 5)
        self.assertTrue(cfg.tn3270.secure)

    def test_get_config_returns_cached_instance(self) -> None:
        importlib.reload(config_module)
        config_module._config = None
        with patch.dict(
            os.environ,
            {
                "VALKEY_HOST": "cache-host",
            },
            clear=False,
        ):
            first = config_module.get_config()

        with patch.dict(
            os.environ,
            {
                "VALKEY_HOST": "new-host",
            },
            clear=False,
        ):
            second = config_module.get_config()

        self.assertIs(first, second)
        self.assertEqual(second.valkey.host, "cache-host")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

