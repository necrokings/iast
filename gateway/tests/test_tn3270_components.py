"""Tests for tn3270 renderer and host helpers."""

from __future__ import annotations

import unittest

from src.services.tn3270.host import Host
from src.services.tn3270.renderer import TN3270Renderer


class _DummyCodec:
    """Simple codec stub that decodes ASCII bytes."""

    def decode(self, data: bytes) -> tuple[str, int]:
        decoded = data.decode("ascii", errors="ignore")
        return decoded, len(decoded)


class _FakeTnz:
    """Lightweight tnz session stub for unit tests."""

    def __init__(
        self,
        rows: int = 1,
        cols: int = 8,
        text: str = " ID: USR",
        attrs: dict[int, int] | None = None,
    ) -> None:
        self.maxrow = rows
        self.maxcol = cols
        self._size = rows * cols
        padded_text = text.ljust(self._size)
        self.plane_dc = [ord(ch) for ch in padded_text[: self._size]]
        self.plane_fa = [0] * self._size
        if attrs:
            for addr, value in attrs.items():
                self.plane_fa[addr % self._size] = value
                self.plane_dc[addr % self._size] = 0
        self.plane_fg = [0] * self._size
        self.plane_bg = [0] * self._size
        self.plane_eh = [0] * self._size
        self.codec_info = {0: _DummyCodec()}
        self.curadd = 1
        self.pwait = 0
        self.updated = 1
        self.commands: list[tuple[str, str | None]] = []

    # ------------------------------------------------------------------
    # Basic tnz operations used by Host/TN3270Renderer
    # ------------------------------------------------------------------
    def scrstr(self, start: int, end: int) -> str:
        start = max(0, start)
        end = min(self._size, end)
        chars = []
        for idx in range(start, end):
            val = self.plane_dc[idx]
            chars.append(chr(val) if val else " ")
        return "".join(chars)

    def set_cursor_position(self, row: int, col: int) -> None:
        # tnz uses 1-indexed coordinates
        self.curadd = (row - 1) * self.maxcol + (col - 1)

    def key_eraseeof(self) -> None:
        self.commands.append(("eraseeof", None))

    def key_data(self, value: str) -> None:
        self.commands.append(("data", value))

    def key_eraseinput(self, value: str | None) -> None:  # pragma: no cover - helper
        self.commands.append(("eraseinput", value))


def _build_test_session() -> _FakeTnz:
    # Field attribute bytes: protected label at 0, unprotected input at 4
    attrs = {
        0: 0x28,  # Protected + intensified
        4: 0x04,  # Unprotected, intensified
    }
    session = _FakeTnz(rows=1, cols=8, text=" ID: USR", attrs=attrs)
    session.curadd = 6  # Cursor inside unprotected field
    return session


class TN3270RendererTests(unittest.TestCase):
    """Validate screen rendering helpers."""

    def setUp(self) -> None:
        self.session = _build_test_session()
        self.renderer = TN3270Renderer()

    def test_render_screen_with_fields_builds_metadata(self) -> None:
        screen = self.renderer.render_screen_with_fields(self.session)

        self.assertTrue(screen.ansi.startswith("\x1b[2J\x1b[H"))
        self.assertEqual(screen.cursor_col, self.session.curadd % self.session.maxcol)
        self.assertEqual(len(screen.fields), 2)
        self.assertTrue(screen.fields[0].protected)
        self.assertFalse(screen.fields[1].protected)
        self.assertEqual(screen.fields[1].length, 3)

    def test_render_screen_and_diff(self) -> None:
        full_render = self.renderer.render_screen(self.session)
        diff_render = self.renderer.render_diff(self.session, prev_screen=b"prior")
        self.assertEqual(full_render, diff_render)
        self.assertIn("\x1b[0m", full_render)

    def test_is_position_protected_uses_field_map(self) -> None:
        self.assertTrue(self.renderer.is_position_protected(self.session, 0, 1))
        self.assertFalse(self.renderer.is_position_protected(self.session, 0, 6))

    def test_cursor_and_size_helpers(self) -> None:
        cursor_row, cursor_col = self.renderer.get_cursor_position(self.session)
        rows, cols = self.renderer.get_screen_size(self.session)
        self.assertEqual(cursor_row, self.session.curadd // self.session.maxcol)
        self.assertEqual(cursor_col, self.session.curadd % self.session.maxcol)
        self.assertEqual((rows, cols), (self.session.maxrow, self.session.maxcol))

    def test_decode_char_and_attr_sequences(self) -> None:
        class _Codec:
            def decode(self, data: bytes):
                return ("@", len(data))

        class _DecodeStub:
            codec_info = {0: _Codec()}

        decoded = self.renderer._decode_char(0x41, _DecodeStub())  # type: ignore[arg-type]
        self.assertEqual(decoded, "@")

        class _FallbackStub:
            codec_info: dict[int, object] = {}

        fallback_char = self.renderer._decode_char(0xC1, _FallbackStub())  # type: ignore[arg-type]
        self.assertEqual(fallback_char, "A")

        class _ErrorStub:
            codec_info = {0: object()}

        error_char = self.renderer._decode_char(0x00, _ErrorStub())  # type: ignore[arg-type]
        self.assertEqual(error_char, " ")

        seq_default = self.renderer._build_attr_sequence(2, 0, 0)
        seq_blink = self.renderer._build_attr_sequence(3, 1, 0xF1)
        seq_reverse = self.renderer._build_attr_sequence(4, 2, 0xF2)
        seq_underscore = self.renderer._build_attr_sequence(5, 3, 0xF4)
        self.assertIn("32", seq_default)
        self.assertIn("5", seq_blink)
        self.assertIn("7", seq_reverse)
        self.assertIn("4", seq_underscore)


class HostTests(unittest.TestCase):
    """Exercise high-level tn3270 host helpers."""

    def test_get_fields_and_find_field_by_label(self) -> None:
        session = _build_test_session()
        host = Host(session)

        fields = host.get_fields()

        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0].value, "ID:")
        self.assertEqual(fields[1].value, "USR")

        input_field = host.find_field_by_label("ID")
        self.assertIsNotNone(input_field)
        assert input_field is not None
        self.assertFalse(input_field.protected)

    def test_fill_field_by_label_moves_cursor_and_types(self) -> None:
        session = _build_test_session()
        host = Host(session)

        filled = host.fill_field_by_label("ID", "NEW")

        self.assertTrue(filled)
        # Cursor should land at start of unprotected field (address 5)
        self.assertEqual(session.curadd, host.get_fields()[1].address)
        self.assertIn(("eraseeof", None), session.commands)
        self.assertIn(("data", "NEW"), session.commands)

    def test_get_formatted_screen_includes_row_numbers(self) -> None:
        session = _build_test_session()
        host = Host(session)

        formatted = host.get_formatted_screen()

        self.assertIn("01", formatted.splitlines()[0])
        self.assertIn("ID:", formatted)

    def test_snapshot_returns_structure(self) -> None:
        session = _build_test_session()
        host = Host(session)
        session.pwait = 1

        snap = host.snapshot()

        self.assertEqual(snap["rows"], 1)
        self.assertTrue(snap["keyboard_locked"])
        self.assertEqual(len(snap["fields"]), 2)


if __name__ == "__main__":
    unittest.main()
