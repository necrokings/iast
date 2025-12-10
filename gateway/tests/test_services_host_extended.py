"""Extended coverage for the TN3270 Host helper."""

from __future__ import annotations

import threading
import time
import unittest

import src.services.tn3270.host as host_module
from src.services.tn3270.host import (
    FA_HIDDEN,
    FA_INTENSIFIED,
    FA_PROTECTED,
    Host,
)


class DummyCodec:
    def decode(self, data: bytes):
        return (data.decode("ascii"), len(data))


class FakeTnz:
    """A lightweight stand-in for tnz.Tnz that exposes the attributes Host needs."""

    def __init__(self) -> None:
        self.maxrow = 2
        self.maxcol = 10
        self.curadd = 1
        self.pwait = 0
        self.updated = 0
        self._wait_calls = 0
        self.codec_info = {0: DummyCodec()}
        self.commands: list[tuple[str, str | None]] = []

        size = self.maxrow * self.maxcol
        self.plane_fa = [0] * size
        self.plane_dc = [ord(" ")] * size

        # Configure protected label "User" followed by input field
        self._define_field(0, FA_PROTECTED | FA_INTENSIFIED, "User")
        self._define_field(5, 0x01, "    ")
        # Hidden password field
        self._define_field(10, FA_PROTECTED | FA_HIDDEN, "Pass")
        self._define_field(15, 0x01, "    ")

        self.enter_called_with: str | None = None
        self.clear_called = False
        self.pf_pressed: int | None = None
        self.pa_pressed: int | None = None
        self.attn_called = False

        for i in range(1, 25):
            setattr(self, f"pf{i}", self._make_pf(i))
        for i in range(1, 4):
            setattr(self, f"pa{i}", self._make_pa(i))

    def _define_field(self, attr_pos: int, attr: int, text: str) -> None:
        self.plane_fa[attr_pos] = attr
        pointer = (attr_pos + 1) % (self.maxrow * self.maxcol)
        for ch in text:
            self.plane_dc[pointer] = ord(ch)
            pointer = (pointer + 1) % (self.maxrow * self.maxcol)

    def _make_pf(self, number: int):
        def _pf():
            self.pf_pressed = number

        return _pf

    def _make_pa(self, number: int):
        def _pa():
            self.pa_pressed = number

        return _pa

    def scrstr(self, start: int, end: int) -> str:
        chars: list[str] = []
        for index in range(start, end):
            idx = index % (self.maxrow * self.maxcol)
            if self.plane_fa[idx]:
                chars.append(" ")
            else:
                chars.append(chr(self.plane_dc[idx]))
        return "".join(chars)

    def set_cursor_position(self, row: int, col: int) -> None:
        self.curadd = (row - 1) * self.maxcol + (col - 1)

    def key_home(self) -> None:
        self.curadd = 1

    def key_tab(self) -> None:
        self.curadd = (self.curadd + 5) % (self.maxrow * self.maxcol)

    def key_backtab(self) -> None:
        self.curadd = (self.curadd - 5) % (self.maxrow * self.maxcol)

    def key_eraseeof(self) -> None:
        field_end = self.curadd + 4
        for idx in range(self.curadd, field_end):
            self.plane_dc[idx % (self.maxrow * self.maxcol)] = ord(" ")
        self.commands.append(("eraseeof", None))

    def key_data(self, value: str) -> None:
        for ch in value:
            self.plane_dc[self.curadd] = ord(ch)
            self.curadd = (self.curadd + 1) % (self.maxrow * self.maxcol)
        self.commands.append(("data", value))

    def key_eraseinput(self, _arg) -> None:
        self.plane_dc = [ord(" ")] * (self.maxrow * self.maxcol)
        self.commands.append(("eraseinput", None))

    def key_backspace(self) -> None:
        self.curadd = (self.curadd - 1) % (self.maxrow * self.maxcol)
        self.plane_dc[self.curadd] = ord(" ")
        self.commands.append(("backspace", None))

    def key_delete(self) -> None:
        self.plane_dc[self.curadd] = ord(" ")
        self.commands.append(("delete", None))

    def enter(self, text: str | None = None) -> None:
        self.enter_called_with = text or ""

    def clear(self) -> None:
        self.clear_called = True

    def attn(self) -> None:
        self.attn_called = True

    def wait(self, timeout: float = 0.0) -> bool:
        self._wait_calls += 1
        if self._wait_calls > 1:
            self.pwait = 0
        time.sleep(timeout or 0)
        updated = bool(self.updated)
        self.updated = 0
        return updated


class HostExtendedTests(unittest.TestCase):
    """Broader coverage for Host behavior."""

    def setUp(self) -> None:
        self.tnz = FakeTnz()
        self.host = Host(self.tnz)
        self.addCleanup(self._restore_log)
        self._original_log = host_module.log
        host_module.log = host_module.log  # ensure attribute exists

    def _restore_log(self) -> None:
        host_module.log = self._original_log

    class _DummyLog:
        def __init__(self) -> None:
            self.messages: list[str] = []
            self.warn_messages: list[str] = []

        def info(self, message: str, **kwargs) -> None:  # type: ignore[override]
            self.messages.append(message)

        def warning(self, message: str, **kwargs) -> None:  # type: ignore[override]
            self.warn_messages.append(message)

        def error(self, message: str, **kwargs) -> None:  # type: ignore[override]
            self.messages.append(message)

    def test_screen_helpers(self) -> None:
        formatted = self.host.get_formatted_screen(show_row_numbers=False)
        self.assertIn("User", formatted)
        redacted = self.host.show_screen("LOGIN")
        self.assertIn("User", redacted)
        self.assertTrue(self.host.get_text(0, 0, 4).strip().startswith("Use"))
        self.assertIn("User", self.host.get_row(0))
        position = self.host.find_text("User")
        self.assertIsNotNone(position)
        self.assertTrue(self.host.screen_contains("user", case_sensitive=False))

    def test_show_screen_redacts_password_and_logs_without_title(self) -> None:
        dummy_log = self._DummyLog()
        host_module.log = dummy_log  # type: ignore[assignment]
        temp_tnz = FakeTnz()
        temp_host = Host(temp_tnz)
        size = temp_tnz.maxrow * temp_tnz.maxcol
        temp_tnz.plane_fa = [0] * size
        payload = "Password.... secret Passcode.... 123"
        for idx, ch in enumerate(payload.ljust(size)[:size]):
            temp_tnz.plane_dc[idx] = ord(ch)

        redacted = temp_host.show_screen(title=None)

        self.assertRegex(redacted.replace("\n", " "), r"Password\.+\s+\*+")
        self.assertTrue(any("=" in msg for msg in dummy_log.messages))

    def test_get_formatted_screen_handles_empty(self) -> None:
        original_scrstr = self.tnz.scrstr

        def empty_scrstr(start: int, end: int) -> str:
            return ""

        self.tnz.scrstr = empty_scrstr  # type: ignore[assignment]
        self.assertEqual("", self.host.get_formatted_screen())
        self.tnz.scrstr = original_scrstr  # type: ignore[assignment]

    def test_field_discovery_and_fill(self) -> None:
        fields = self.host.get_fields()
        self.assertEqual(len(fields), 4)
        self.assertEqual(len(self.host.get_protected_fields()), 2)
        self.assertEqual(len(self.host.get_unprotected_fields()), 2)
        hidden_field = next((f for f in fields if f.hidden), None)
        self.assertIsNotNone(hidden_field)

        field = self.host.find_field_by_label("User")
        self.assertIsNotNone(field)
        self.assertTrue(self.host.fill_field_by_label("User", "ABCD"))

        self.host.move_cursor_to_address(field.address)
        current_field = self.host.find_field_at_cursor()
        self.assertIsNotNone(current_field)
        self.assertEqual(current_field.value.strip(), "ABCD")

    def test_find_field_by_label_case_sensitive_and_missing_logs_warning(self) -> None:
        dummy_log = self._DummyLog()
        host_module.log = dummy_log  # type: ignore[assignment]

        field = self.host.find_field_by_label("USER", case_sensitive=True)
        self.assertIsNone(field)
        self.assertFalse(self.host.fill_field_by_label("DoesNotExist", "val"))
        self.assertTrue(dummy_log.warn_messages)

    def test_cursor_and_key_operations(self) -> None:
        self.host.move_cursor(0, 0)
        self.host.home()
        self.host.tab()
        self.host.backtab()
        self.host.move_cursor_to_address(5)

        self.host.fill_field_at_cursor("XYZ")
        self.host.fill_field_at_position(1, 1, "LMN", clear_first=False)
        self.host.type_text("12")
        self.host.clear_field()
        self.host.clear_all_fields()
        self.host.backspace()
        self.host.delete()
        self.host.enter("cmd")
        self.host.clear()
        self.host.pf(2)
        self.host.pa(1)
        self.host.attn()

        self.assertEqual(self.tnz.enter_called_with, "cmd")
        self.assertTrue(self.tnz.clear_called)
        self.assertEqual(self.tnz.pf_pressed, 2)
        self.assertEqual(self.tnz.pa_pressed, 1)
        self.assertTrue(self.tnz.attn_called)

    def test_pf_and_pa_invalid_keys_raise(self) -> None:
        with self.assertRaises(ValueError):
            self.host.pf(0)
        with self.assertRaises(ValueError):
            self.host.pa(0)

    def test_find_field_at_cursor_wraparound(self) -> None:
        self.tnz._define_field(self.tnz.maxrow * self.tnz.maxcol - 1, FA_PROTECTED, "W")
        self.tnz.curadd = 0
        field = self.host.find_field_at_cursor()
        self.assertIsNotNone(field)

    def test_fill_field_at_cursor_without_clear(self) -> None:
        self.host.move_cursor_to_address(5)
        self.host.fill_field_at_cursor("XY", clear_first=False)
        self.assertIn(("data", "XY"), self.tnz.commands)

    def test_cursor_and_typing_operations(self) -> None:
        self.host.move_cursor(0, 1)
        self.host.fill_field_at_cursor("ZZ")
        self.host.fill_field_at_position(1, 5, "XY", clear_first=False)
        self.host.type_text("123")
        self.host.clear_field()
        self.host.clear_all_fields()
        self.host.move_cursor_to_address(5)
        self.host.backspace()
        self.host.delete()
        self.host.home()
        self.host.tab()
        self.host.backtab()

    def test_aid_and_action_keys(self) -> None:
        self.host.enter("hello")
        self.host.clear()
        self.host.pf(3)
        self.host.pa(2)
        self.host.attn()
        self.assertEqual(self.tnz.enter_called_with, "hello")
        self.assertTrue(self.tnz.clear_called)
        self.assertEqual(self.tnz.pf_pressed, 3)
        self.assertEqual(self.tnz.pa_pressed, 2)
        self.assertTrue(self.tnz.attn_called)

    def test_wait_and_snapshot(self) -> None:
        self.tnz.updated = 1
        self.assertTrue(self.host.wait(timeout=0.01))
        self.tnz.pwait = 1

        def unlock():
            time.sleep(0.05)
            self.tnz.pwait = 0

        threading.Thread(target=unlock, daemon=True).start()
        self.assertTrue(self.host.wait_for_keyboard(timeout=1))
        self.assertTrue(self.host.wait_for_text("User"))

        snap = self.host.snapshot()
        self.assertIn("cursor", snap)
        self.assertIn("fields", snap)
        self.assertIn("rows", snap)
        self.assertIn("cols", snap)
        self.assertIn("keyboard_locked", snap)
        self.assertIn("Host", repr(self.host))

    def test_wait_for_text_timeout_and_keyboard_timeout(self) -> None:
        self.host.screen_contains = lambda *args, **kwargs: False  # type: ignore[assignment]
        self.assertFalse(self.host.wait_for_text("Never", timeout=0.01))

        self.tnz.pwait = 1
        self.host.wait = lambda timeout=0.1: False  # type: ignore[assignment]
        self.assertFalse(self.host.wait_for_keyboard(timeout=0.05))

    def test_basic_properties(self) -> None:
        self.assertEqual(self.host.rows, self.tnz.maxrow)
        self.assertEqual(self.host.cols, self.tnz.maxcol)
        self.assertEqual(self.host.cursor_row, self.tnz.curadd // self.tnz.maxcol)
        self.assertEqual(self.host.cursor_col, self.tnz.curadd % self.tnz.maxcol)
        self.assertEqual(self.host.cursor_position.row, self.host.cursor_row)
        self.assertIsInstance(self.host.screen, str)
        self.tnz.pwait = 1
        self.assertTrue(self.host.is_keyboard_locked)
        self.tnz.updated = 1
        self.assertTrue(self.host.did_screen_update)

        snap = self.host.snapshot()
        self.assertIn("cursor", snap)
        self.assertIn("fields", snap)
        self.assertIn("rows", snap)
        self.assertIn("cols", snap)
        self.assertIn("keyboard_locked", snap)
        self.assertIn("Host", repr(self.host))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
