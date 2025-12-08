"""Coverage for BaseMessage behaviors."""

from __future__ import annotations

import importlib
import time
import unittest

import src.models.base as base_module


class BaseMessageTests(unittest.TestCase):
    """Ensure shared message fields behave consistently."""

    @classmethod
    def setUpClass(cls) -> None:
        importlib.reload(base_module)

    def test_alias_population_and_dump(self) -> None:
        msg = base_module.BaseMessage(sessionId="sess-1", payload="hello world")

        self.assertEqual(msg.session_id, "sess-1")
        self.assertEqual(msg.payload, "hello world")
        dumped = msg.model_dump(by_alias=True)
        self.assertEqual(dumped["sessionId"], "sess-1")
        self.assertEqual(dumped["payload"], "hello world")

    def test_default_timestamp_is_recent(self) -> None:
        before = int(time.time() * 1000) - 5
        msg = base_module.BaseMessage(sessionId="sess-2")
        after = int(time.time() * 1000) + 5

        self.assertGreaterEqual(msg.timestamp, before)
        self.assertLessEqual(msg.timestamp, after)

    def test_overrides_available(self) -> None:
        msg = base_module.BaseMessage(
            sessionId="sess-3",
            timestamp=1234567890,
            encoding="ascii",
            seq=42,
            payload="custom",
        )

        self.assertEqual(msg.timestamp, 1234567890)
        self.assertEqual(msg.encoding, "ascii")
        self.assertEqual(msg.seq, 42)
        self.assertEqual(msg.payload, "custom")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
