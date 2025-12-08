"""Covers the collection of message model helpers."""

from __future__ import annotations

import unittest

from src.models.data import DataMessage, create_data_message
from src.models.error import ErrorMessage, ErrorMeta, create_error_message
from src.models.ping import PingMessage, PongMessage
from src.models.session import (
    SessionCreateMessage,
    SessionCreateMeta,
    SessionCreatedMessage,
    SessionCreatedMeta,
    SessionDestroyedMessage,
    SessionDestroyedMeta,
    SessionDestroyMessage,
    create_session_created_message,
    create_session_destroyed_message,
)
from src.models.tn3270 import (
    TN3270CursorMeta,
    TN3270CursorMessage,
    TN3270Field,
    TN3270ScreenMessage,
    TN3270ScreenMeta,
    create_tn3270_cursor_message,
    create_tn3270_screen_message,
)


class AllMessagesTests(unittest.TestCase):
    """Ensure each message class can be instantiated and behaves as expected."""

    def test_data_and_error_messages(self) -> None:
        data_msg = create_data_message("sess", "payload")
        self.assertIsInstance(data_msg, DataMessage)
        self.assertEqual(data_msg.payload, "payload")

        err_msg = create_error_message("sess", "E1", "bad")
        self.assertIsInstance(err_msg, ErrorMessage)
        self.assertIsInstance(err_msg.meta, ErrorMeta)
        self.assertEqual(err_msg.meta.code, "E1")

    def test_ping_pong_messages(self) -> None:
        ping = PingMessage(sessionId="sess")
        pong = PongMessage(sessionId="sess")
        self.assertEqual(ping.type.value, "ping")
        self.assertEqual(pong.type.value, "pong")

    def test_session_messages(self) -> None:
        create_msg = SessionCreateMessage(sessionId="sess", meta=SessionCreateMeta(cols=80))
        destroy_msg = SessionDestroyMessage(sessionId="sess")
        created_msg = create_session_created_message("sess", "shell", 123)
        destroyed_msg = create_session_destroyed_message("sess", "done")

        self.assertIsInstance(create_msg.meta, SessionCreateMeta)
        self.assertIsInstance(destroy_msg, SessionDestroyMessage)
        self.assertIsInstance(created_msg.meta, SessionCreatedMeta)
        self.assertIsInstance(destroyed_msg.meta, SessionDestroyedMeta)

    def test_tn3270_messages(self) -> None:
        fields = [
            TN3270Field(
                start=0,
                end=5,
                protected=False,
                intensified=True,
                row=0,
                col=0,
                length=5,
            )
        ]
        screen_msg = create_tn3270_screen_message(
            session_id="sess",
            ansi_data="ansi",
            fields=fields,
            cursor_row=1,
            cursor_col=2,
            rows=24,
            cols=80,
        )
        cursor_msg = create_tn3270_cursor_message("sess", row=1, col=2)

        self.assertIsInstance(screen_msg.meta, TN3270ScreenMeta)
        self.assertIsInstance(cursor_msg.meta, TN3270CursorMeta)
        self.assertEqual(cursor_msg.meta.col, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

