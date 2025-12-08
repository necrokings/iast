"""Additional coverage for message helpers."""

from __future__ import annotations

import unittest

from src.models import data as data_module
from src.models import error as error_module
from src.models import session as session_module
from src.models import tn3270 as tn3270_module
from src.models import types as types_module


class MessageFactoryTests(unittest.TestCase):
    """Verify small helper constructors behave as expected."""

    def test_create_data_message_sets_payload_and_type(self) -> None:
        msg = data_module.create_data_message("session-1", "hello world")

        self.assertIsInstance(msg, data_module.DataMessage)
        self.assertEqual(msg.session_id, "session-1")
        self.assertEqual(msg.payload, "hello world")
        self.assertEqual(msg.type, types_module.MessageType.DATA)

    def test_create_error_message_populates_meta(self) -> None:
        msg = error_module.create_error_message("session-2", "E777", "boom")

        self.assertIsInstance(msg, error_module.ErrorMessage)
        self.assertEqual(msg.meta.code, "E777")
        self.assertEqual(msg.payload, "boom")
        self.assertEqual(msg.type, types_module.MessageType.ERROR)

    def test_session_helpers_return_expected_models(self) -> None:
        create_msg = session_module.SessionCreateMessage(
            sessionId="session-3",
            meta=session_module.SessionCreateMeta(shell="bash", env={"FOO": "BAR"}),
        )
        self.assertEqual(create_msg.meta.shell, "bash")
        self.assertEqual(create_msg.meta.env, {"FOO": "BAR"})

        created_msg = session_module.create_session_created_message("session-3", "bash", 1234)
        self.assertIsInstance(created_msg, session_module.SessionCreatedMessage)
        self.assertEqual(created_msg.meta.pid, 1234)

        destroyed_msg = session_module.create_session_destroyed_message("session-3", "done")
        self.assertIsInstance(destroyed_msg, session_module.SessionDestroyedMessage)
        self.assertEqual(destroyed_msg.payload, "done")
        self.assertIsInstance(destroyed_msg.meta, session_module.SessionDestroyedMeta)

    def test_tn3270_helpers_build_meta_payloads(self) -> None:
        fields = [
            tn3270_module.TN3270Field(
                start=0,
                end=5,
                protected=False,
                intensified=False,
                row=0,
                col=0,
                length=5,
            )
        ]
        screen_msg = tn3270_module.create_tn3270_screen_message(
            "session-5",
            ansi_data="ansi",
            fields=fields,
            cursor_row=10,
            cursor_col=20,
            rows=24,
            cols=80,
        )
        self.assertIsInstance(screen_msg, tn3270_module.TN3270ScreenMessage)
        self.assertEqual(screen_msg.payload, "ansi")
        self.assertEqual(screen_msg.meta.fields[0].start, 0)
        self.assertEqual(screen_msg.meta.cursorRow, 10)
        self.assertEqual(screen_msg.meta.cursorCol, 20)

        cursor_msg = tn3270_module.create_tn3270_cursor_message("session-5", row=3, col=4)
        self.assertIsInstance(cursor_msg, tn3270_module.TN3270CursorMessage)
        self.assertEqual(cursor_msg.meta.row, 3)
        self.assertEqual(cursor_msg.meta.col, 4)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

