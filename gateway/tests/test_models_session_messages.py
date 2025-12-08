"""Session message helpers coverage."""

from __future__ import annotations

import unittest

from src.models.session import (
    SessionCreateMessage,
    SessionCreateMeta,
    SessionCreatedMessage,
    SessionDestroyedMessage,
    SessionDestroyedMeta,
    SessionDestroyMessage,
    create_session_created_message,
    create_session_destroyed_message,
)


class SessionMessageTests(unittest.TestCase):
    """Validate the small message helper utilities."""

    def test_session_create_message_defaults(self) -> None:
        msg = SessionCreateMessage(sessionId="sess", meta=SessionCreateMeta(shell="bash"))
        self.assertEqual(msg.session_id, "sess")
        self.assertEqual(msg.meta.shell, "bash")

    def test_session_destroy_message_has_payload(self) -> None:
        msg = SessionDestroyMessage(sessionId="sess-d")
        self.assertEqual(msg.payload, "")

    def test_create_session_created_message_populates_meta(self) -> None:
        msg = create_session_created_message("sess", "shell", 123)
        self.assertIsInstance(msg, SessionCreatedMessage)
        self.assertEqual(msg.meta.shell, "shell")
        self.assertEqual(msg.meta.pid, 123)

    def test_create_session_destroyed_message_sets_reason(self) -> None:
        msg = create_session_destroyed_message("sess", "done")
        self.assertIsInstance(msg, SessionDestroyedMessage)
        self.assertIsInstance(msg.meta, SessionDestroyedMeta)
        self.assertEqual(msg.payload, "done")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

