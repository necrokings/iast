"""Tests for the gateway messaging API."""

from __future__ import annotations

import json
import unittest

from src.models import (
    DataMessage,
    create_ast_progress_message,
    create_session_created_message,
    parse_message,
    serialize_message,
)


class MessageParserTests(unittest.TestCase):
    """Validate parsing and serialization of gateway messages."""

    def test_parse_message_returns_data_message(self) -> None:
        raw = json.dumps(
            {
                "sessionId": "session-123",
                "type": "data",
                "payload": "hello",
            }
        )

        msg = parse_message(raw)

        self.assertIsInstance(msg, DataMessage)
        self.assertEqual(msg.session_id, "session-123")
        self.assertEqual(msg.payload, "hello")

    def test_parse_message_accepts_bytes_and_meta_aliases(self) -> None:
        raw = json.dumps(
            {
                "sessionId": "session-456",
                "type": "session.create",
                "meta": {
                    "shell": "tn3270.example.com:23",
                    "cols": 80,
                    "rows": 43,
                },
            }
        ).encode("utf-8")

        msg = parse_message(raw)

        self.assertEqual(msg.session_id, "session-456")
        self.assertIsNotNone(msg.meta)
        assert msg.meta  # appease the type checker
        self.assertEqual(msg.meta.shell, "tn3270.example.com:23")
        self.assertEqual(msg.meta.cols, 80)
        self.assertEqual(msg.meta.rows, 43)

    def test_parse_message_rejects_unknown_types(self) -> None:
        raw = json.dumps({"sessionId": "session-789", "type": "unknown"})

        with self.assertRaises(ValueError):
            parse_message(raw)


class MessageFactoryTests(unittest.TestCase):
    """Ensure factory helpers keep API contracts stable."""

    def test_serialize_message_preserves_aliases(self) -> None:
        msg = create_session_created_message(
            "session-alias",
            "tn3270://example:23",
            pid=42,
        )

        payload = json.loads(serialize_message(msg))

        self.assertEqual(payload["sessionId"], "session-alias")
        self.assertEqual(payload["meta"]["shell"], "tn3270://example:23")
        self.assertEqual(payload["meta"]["pid"], 42)

    def test_create_ast_progress_message_calculates_percentages(self) -> None:
        msg = create_ast_progress_message(
            session_id="session-p",
            execution_id="exec-1",
            ast_name="login",
            current=2,
            total=3,
            message="Processing item",
        )

        self.assertEqual(msg.meta.percent, 67)
        self.assertEqual(msg.payload, "Processing item")
        self.assertEqual(msg.meta.execution_id, "exec-1")
        self.assertEqual(msg.meta.ast_name, "login")

