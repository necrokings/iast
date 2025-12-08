"""Coverage for TN3270 message models."""

from __future__ import annotations

import importlib
import unittest

import src.models.tn3270 as tn3270_module


class TN3270MessageTests(unittest.TestCase):
    """Ensure TN3270 message helpers behave predictably."""

    @classmethod
    def setUpClass(cls) -> None:
        importlib.reload(tn3270_module)

    def setUp(self) -> None:
        self.fields = [
            tn3270_module.TN3270Field(
                start=0,
                end=5,
                protected=True,
                intensified=False,
                row=0,
                col=0,
                length=5,
            ),
            tn3270_module.TN3270Field(
                start=5,
                end=10,
                protected=False,
                intensified=True,
                row=0,
                col=5,
                length=5,
            ),
        ]

    def test_field_model_serialization(self) -> None:
        data = self.fields[0].model_dump()
        restored = tn3270_module.TN3270Field.model_validate(data)
        self.assertEqual(restored.start, 0)
        self.assertTrue(restored.protected)
        self.assertTrue(self.fields[1].is_input())
        self.assertEqual(self.fields[0].span(), (0, 5))

    def test_screen_message_factory(self) -> None:
        message = tn3270_module.create_tn3270_screen_message(
            session_id="sess",
            ansi_data="ANSI",
            fields=self.fields,
            cursor_row=1,
            cursor_col=2,
            rows=24,
            cols=80,
        )

        self.assertIsInstance(message, tn3270_module.TN3270ScreenMessage)
        meta = message.meta
        self.assertIsInstance(meta, tn3270_module.TN3270ScreenMeta)
        self.assertEqual(meta.cursorRow, 1)
        self.assertEqual(meta.fields[1].col, 5)
        self.assertEqual(meta.cursor_position(), (1, 2))
        self.assertEqual(message.field_count(), 2)

    def test_cursor_message_factory(self) -> None:
        message = tn3270_module.create_tn3270_cursor_message("sess", row=3, col=4)
        self.assertIsInstance(message, tn3270_module.TN3270CursorMessage)
        self.assertIsInstance(message.meta, tn3270_module.TN3270CursorMeta)
        self.assertEqual(message.meta.row, 3)
        self.assertEqual(message.meta.col, 4)
        self.assertEqual(message.meta.as_tuple(), (3, 4))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

