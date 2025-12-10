# ============================================================================
# TN3270 Host Automation Service
# ============================================================================
"""
High-level automation service for interacting with 3270 terminals.

Provides convenient methods for:
- Screen reading and field discovery
- Field-based input (find by label, fill by cursor/label)
- Key sending (PF keys, PA keys, Enter, Clear, etc.)
- Cursor navigation
- Wait/sync operations

This service wraps tnz operations for use in automation scripts.
"""

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from tnz.tnz import Tnz

log = structlog.get_logger()

# Field attribute bit masks
FA_PROTECTED = 0x20
FA_INTENSIFIED = 0x08
FA_HIDDEN = 0x0C  # Non-display bits


@dataclass
class ScreenField:
    """Represents a field on the 3270 screen."""

    address: int  # Linear buffer address (0-indexed)
    row: int  # Row (0-indexed)
    col: int  # Column (0-indexed)
    length: int  # Field length
    protected: bool  # True if protected (no input)
    intensified: bool  # True if intensified
    hidden: bool  # True if hidden (password field)
    value: str  # Current field content


@dataclass
class ScreenPosition:
    """Represents a position on the screen."""

    row: int  # Row (0-indexed)
    col: int  # Column (0-indexed)
    address: int  # Linear buffer address


class Host:
    """
    High-level automation interface for a TN3270 session.

    Example usage:
        host = Host(tnz_session)

        # Wait for screen and show it
        host.wait()
        print(host.screen)

        # Find and fill a field by its label
        host.fill_field_by_label("Userid", "MYUSER")
        host.fill_field_by_label("Password", "MYPASS")

        # Send Enter
        host.enter()

        # Wait for response
        host.wait()
    """

    def __init__(self, tnz: "Tnz") -> None:
        """
        Initialize Host with a tnz session.

        Args:
            tnz: An active tnz.Tnz session object
        """
        self._tnz = tnz

    # =========================================================================
    # Screen Properties
    # =========================================================================

    @property
    def rows(self) -> int:
        """Get the number of rows on the screen."""
        return self._tnz.maxrow

    @property
    def cols(self) -> int:
        """Get the number of columns on the screen."""
        return self._tnz.maxcol

    @property
    def cursor_row(self) -> int:
        """Get current cursor row (0-indexed)."""
        return self._tnz.curadd // self._tnz.maxcol

    @property
    def cursor_col(self) -> int:
        """Get current cursor column (0-indexed)."""
        return self._tnz.curadd % self._tnz.maxcol

    @property
    def cursor_position(self) -> ScreenPosition:
        """Get current cursor position."""
        return ScreenPosition(
            row=self.cursor_row,
            col=self.cursor_col,
            address=self._tnz.curadd,
        )

    @property
    def screen(self) -> str:
        """
        Get the full screen content as a multi-line string.

        Returns:
            The screen content with newlines between rows.
        """
        max_rows = self.rows
        max_cols = self.cols
        return self._tnz.scrstr(0, max_rows * max_cols)

    @property
    def is_keyboard_locked(self) -> bool:
        """Check if keyboard input is inhibited."""
        return bool(self._tnz.pwait)

    @property
    def did_screen_update(self) -> bool:
        """Check if screen was updated since last check."""
        return bool(self._tnz.updated)

    # =========================================================================
    # Screen Reading
    # =========================================================================
    def get_formatted_screen(self, show_row_numbers: bool = True) -> str:
        """
        Get the full screen with a border for display.

        Returns:
            Formatted screen with row numbers and border.
        """
        try:
            max_rows = self.rows
            max_cols = self.cols
            screen_text = self._tnz.scrstr(0, max_rows * max_cols)
            if not screen_text:
                return ""
            lines = []
            for row in range(max_rows):
                start = row * max_cols
                end = start + max_cols
                line_text = screen_text[start:end].rstrip()
                if show_row_numbers:
                    lines.append(f"{row + 1:02d} {line_text}")
                else:
                    lines.append(line_text)
            return "\n".join(lines)
        except Exception:
            return ""

    def show_screen(self, title: str = "SCREEN") -> str:
        """
        Get the full screen with a border for display.

        Args:
            title: Title to display in the header (default: "SCREEN")

        Returns:
            Formatted screen with row numbers and border.
        """
        screen_content = self.get_formatted_screen(show_row_numbers=True)
        screen_content = re.sub(
            r"(Password\.+\s+)(\S+)", r"\1******", screen_content, flags=re.IGNORECASE
        )
        screen_content = re.sub(
            r"(Passcode\.+\s+)(\S+)", r"\1******", screen_content, flags=re.IGNORECASE
        )
        # Remove empty new lines from screen content which only has row numbers
        screen_content = re.sub(
            r"^\s*\d{2}\s*$\n", "", screen_content, flags=re.MULTILINE
        )
        seperator = "=" * 80
        if title:
            title_text = f" {title} "
            title_line = title_text.center(80, "=")
            # structlog doesn't accept printf-style positional args; format first
            log.info("\n%s\n%s\n%s" % (seperator, title_line, seperator))
            log.info("\n%s" % screen_content)
            log.info("\n%s" % seperator)
        else:
            # format the separator into a single string
            log.info("\n%s" % seperator)
        return screen_content

    def get_text(self, row: int, col: int, length: int) -> str:
        """
        Get text from a specific position on the screen.

        Args:
            row: Row number (0-indexed)
            col: Column number (0-indexed)
            length: Number of characters to read

        Returns:
            The text at the specified position.
        """
        start_addr = row * self.cols + col
        end_addr = start_addr + length
        return self._tnz.scrstr(start_addr, end_addr)

    def get_row(self, row: int) -> str:
        """
        Get a complete row of text.

        Args:
            row: Row number (0-indexed)

        Returns:
            The text content of the row.
        """
        return self.get_text(row, 0, self.cols)

    def find_text(self, text: str, start_row: int = 0) -> ScreenPosition | None:
        """
        Find text on the screen.

        Args:
            text: Text to search for
            start_row: Row to start searching from (0-indexed)

        Returns:
            ScreenPosition if found, None otherwise.
        """
        screen = self.screen
        lines = screen.split("\n")

        for row_idx in range(start_row, len(lines)):
            col_idx = lines[row_idx].find(text)
            if col_idx >= 0:
                return ScreenPosition(
                    row=row_idx,
                    col=col_idx,
                    address=row_idx * self.cols + col_idx,
                )

        return None

    def screen_contains(self, text: str, case_sensitive: bool = False) -> bool:
        """
        Check if the screen contains specific text.

        Args:
            text: Text to search for
            case_sensitive: Whether the text match is case sensitive (default: False)

        Returns:
            True if text is found on the screen.
        """
        search_text = text if case_sensitive else text.lower()
        screen = self.screen if case_sensitive else self.screen.lower()
        return search_text in screen

    # =========================================================================
    # Field Operations
    # =========================================================================

    def get_fields(self) -> list[ScreenField]:
        """
        Get all fields on the screen.

        Returns:
            List of ScreenField objects.
        """
        fields: list[ScreenField] = []
        plane_fa = self._tnz.plane_fa
        plane_dc = self._tnz.plane_dc
        maxcol = self.cols
        maxrow = self.rows
        buffer_size = maxrow * maxcol

        # Find all field attribute positions
        field_starts: list[tuple[int, int]] = []  # (address, attribute)
        for addr in range(buffer_size):
            fa = plane_fa[addr]
            if fa != 0:
                field_starts.append((addr, fa))

        if not field_starts:
            return fields

        # Build field list
        for i, (fa_addr, fa) in enumerate(field_starts):
            # Field starts after the attribute byte
            field_start = (fa_addr + 1) % buffer_size

            # Field ends at the next field attribute (exclusive)
            if i + 1 < len(field_starts):
                field_end = field_starts[i + 1][0]
            else:
                # Wrap around to first field
                field_end = field_starts[0][0]

            # Calculate length
            if field_end > field_start:
                length = field_end - field_start
            else:
                # Wrap-around case
                length = buffer_size - field_start + field_end

            # Get field content
            content_bytes = []
            addr = field_start
            for _ in range(length):
                content_bytes.append(plane_dc[addr])
                addr = (addr + 1) % buffer_size

            # Decode using tnz codec
            try:
                codec_info = self._tnz.codec_info.get(0)
                if codec_info:
                    content, _ = codec_info.decode(bytes(content_bytes))
                else:
                    content = bytes(content_bytes).decode("cp037", errors="replace")
            except Exception:
                content = ""

            # Parse attributes
            protected = bool(fa & FA_PROTECTED)
            intensified = bool(fa & FA_INTENSIFIED)
            hidden = (fa & 0x0C) == FA_HIDDEN

            fields.append(
                ScreenField(
                    address=field_start,
                    row=field_start // maxcol,
                    col=field_start % maxcol,
                    length=length,
                    protected=protected,
                    intensified=intensified,
                    hidden=hidden,
                    value=content.rstrip(),
                )
            )

        return fields

    def get_unprotected_fields(self) -> list[ScreenField]:
        """
        Get all unprotected (input) fields.

        Returns:
            List of unprotected ScreenField objects.
        """
        return [f for f in self.get_fields() if not f.protected]

    def get_protected_fields(self) -> list[ScreenField]:
        """
        Get all protected (display-only) fields.

        Returns:
            List of protected ScreenField objects.
        """
        return [f for f in self.get_fields() if f.protected]

    def find_field_by_label(
        self, label: str, case_sensitive: bool = False
    ) -> ScreenField | None:
        """
        Find an unprotected field by its label.

        Searches the entire screen for the label text, then finds the closest
        unprotected input field after the label position.

        Args:
            label: The label text to search for
            case_sensitive: Whether to match case (default: False)

        Returns:
            The unprotected field following the label, or None.
        """
        try:
            # Get all input fields first
            input_fields = self.get_unprotected_fields()
            if not input_fields:
                return None

            # Get screen dimensions
            maxrow = self.rows
            maxcol = self.cols

            # Get full screen content
            full_screen = self._tnz.scrstr(0, maxrow * maxcol)
            if not full_screen:
                log.warning("Screen buffer is empty")
                return None

            # Prepare search text
            search_text = label if case_sensitive else label.upper()
            screen_text = full_screen if case_sensitive else full_screen.upper()

            # Find label position
            label_pos = screen_text.find(search_text)
            if label_pos == -1:
                log.warning("Label not found on screen", label=label)
                return None

            # Convert buffer position to row/col (0-indexed)
            label_row = label_pos // maxcol
            label_col = label_pos % maxcol
            label_end_col = label_col + len(search_text)

            log.debug(
                "Label found on screen", label=label, row=label_row, col=label_col
            )

            # Find the closest input field after the label
            # Priority: same row to the right, then rows below
            best_field = None
            min_distance = float("inf")

            for field in input_fields:
                field_row = field.row
                field_col = field.col

                # Skip fields that are ABOVE the label
                if field_row < label_row:
                    continue

                # Calculate weighted distance
                row_diff = field_row - label_row

                # For fields on the same row, prefer fields to the right of the label
                if row_diff == 0:
                    if field_col >= label_end_col:
                        # Field is on same row to the right - ideal case
                        col_diff = field_col - label_end_col
                        distance = col_diff
                    else:
                        # Field is on same row but to the left - skip it
                        continue
                else:
                    # Different row (below) - prefer closer rows
                    col_diff = abs(field_col - label_col)
                    distance = row_diff * 1000 + col_diff

                if distance < min_distance:
                    min_distance = distance
                    best_field = field

            if best_field:
                log.debug(
                    "Matched field to label",
                    label=label,
                    field_row=best_field.row,
                    field_col=best_field.col,
                )
            else:
                log.warning("No input field found after label", label=label)

            return best_field

        except Exception as e:
            log.error("Exception in find_field_by_label", label=label, error=str(e))
            return None

    def get_field_value_by_label(self, label: str, case_sensitive: bool = False) -> str:
        """
        Get the value of a field by looking for a nearby label.

        This searches ALL fields (including protected/display fields) to find values.
        Use find_field_by_label() to find input fields for data entry.

        Args:
            label: Label text to search for
            case_sensitive: Whether to perform case-sensitive search

        Returns:
            Field content (str) or empty string if field not found
        """
        try:
            # Get ALL fields (including protected ones with values)
            all_fields = self.get_fields()
            if not all_fields:
                return ""

            # Get screen dimensions
            maxrow = self.rows
            maxcol = self.cols

            # Get full screen content
            full_screen = self._tnz.scrstr(0, maxrow * maxcol)
            if not full_screen:
                return ""

            # Prepare search text
            search_text = label if case_sensitive else label.upper()
            screen_text = full_screen if case_sensitive else full_screen.upper()

            # Find label position
            label_pos = screen_text.find(search_text)
            if label_pos == -1:
                log.warning("Label not found on screen", label=label)
                return ""

            # Convert buffer position to row/col (0-indexed)
            label_row = label_pos // maxcol
            label_col = label_pos % maxcol
            label_end_col = label_col + len(search_text)

            # Find the closest field on the same row, immediately after the label
            best_field = None
            min_distance = float("inf")

            for field in all_fields:
                field_row = field.row
                field_col = field.col

                # Only consider fields on the same row as the label
                if field_row != label_row:
                    continue

                # Only consider fields that start at or after the label ends
                if field_col < label_end_col:
                    continue

                # Calculate distance (prefer closest field to the right)
                distance = field_col - label_end_col

                if distance < min_distance:
                    min_distance = distance
                    best_field = field

            if best_field:
                log.debug("Found field by label", label=label, field=best_field)
                return best_field.value

            log.warning("No field found after label", label=label)
            return ""

        except Exception as e:
            log.error(
                "Exception in get_field_value_by_label", label=label, error=str(e)
            )
            return ""

    def find_field_at_cursor(self) -> ScreenField | None:
        """
        Get the field at the current cursor position.

        Returns:
            The ScreenField at the cursor, or None.
        """
        cursor_addr = self._tnz.curadd
        fields = self.get_fields()

        for field in fields:
            # Check if cursor is within this field
            field_end = field.address + field.length
            buffer_size = self.rows * self.cols

            if field_end > field.address:
                # Normal case
                if field.address <= cursor_addr < field_end:
                    return field
            else:
                # Wrap-around case
                if cursor_addr >= field.address or cursor_addr < field_end:
                    return field

        return None

    # =========================================================================
    # Cursor Movement
    # =========================================================================

    def move_cursor(self, row: int, col: int) -> None:
        """
        Move cursor to a specific position.

        Args:
            row: Row number (0-indexed)
            col: Column number (0-indexed)
        """
        # tnz.set_cursor_position uses 1-indexed coordinates
        self._tnz.set_cursor_position(row + 1, col + 1)

    def move_cursor_to_address(self, address: int) -> None:
        """
        Move cursor to a linear buffer address.

        Args:
            address: Linear buffer address (0-indexed)
        """
        self._tnz.curadd = address

    def home(self) -> None:
        """Move cursor to the first unprotected field."""
        self._tnz.key_home()

    def tab(self) -> None:
        """Move cursor to the next unprotected field."""
        self._tnz.key_tab()

    def backtab(self) -> None:
        """Move cursor to the previous unprotected field."""
        self._tnz.key_backtab()

    # =========================================================================
    # Text Entry
    # =========================================================================

    def fill_field_at_cursor(self, value: str, clear_first: bool = True) -> None:
        """
        Fill the field at the current cursor position.

        Args:
            value: Text to enter
            clear_first: Whether to clear the field first (default: True)
        """
        if clear_first:
            self._tnz.key_eraseeof()
        self._tnz.key_data(value)

    def fill_field_by_label(
        self, label: str, value: str, case_sensitive: bool = False
    ) -> bool:
        """
        Find a field by its label and fill it with a value.

        Args:
            label: The label text to search for
            value: The text to enter
            case_sensitive: Whether to match label case (default: False)

        Returns:
            True if field was found and filled, False otherwise.
        """
        field = self.find_field_by_label(label, case_sensitive)
        if field is None:
            log.warning("Field not found by label", label=label)
            return False

        log.debug("Filling field found by label", label=label, field=field)

        # Move cursor to field start
        self.move_cursor_to_address(field.address)

        # Clear and fill
        self._tnz.key_eraseeof()
        self._tnz.key_data(value)

        return True

    def fill_field_at_position(
        self, row: int, col: int, value: str, clear_first: bool = True
    ) -> None:
        """
        Move cursor to position and fill with value.

        Args:
            row: Row number (0-indexed)
            col: Column number (0-indexed)
            value: Text to enter
            clear_first: Whether to clear the field first (default: True)
        """
        self.move_cursor(row, col)
        if clear_first:
            self._tnz.key_eraseeof()
        self._tnz.key_data(value)

    def type_text(self, text: str) -> None:
        """
        Type text at the current cursor position.

        Args:
            text: Text to type
        """
        self._tnz.key_data(text)

    def clear_field(self) -> None:
        """Clear from cursor to end of current field."""
        self._tnz.key_eraseeof()

    def clear_all_fields(self) -> None:
        """Clear all unprotected fields on the screen."""
        self._tnz.key_eraseinput(None)

    def backspace(self) -> None:
        """Delete character before cursor."""
        self._tnz.key_backspace()

    def delete(self) -> None:
        """Delete character at cursor."""
        self._tnz.key_delete()

    # =========================================================================
    # AID Keys (Actions that send to host)
    # =========================================================================

    def enter(self, text: str | None = None) -> None:
        """
        Send ENTER key.

        Args:
            text: Optional text to type before pressing Enter
        """
        if text:
            self._tnz.enter(text)
        else:
            self._tnz.enter()

    def clear(self) -> None:
        """Send CLEAR key."""
        self._tnz.clear()

    def pf(self, num: int) -> None:
        """
        Send a PF (Program Function) key.

        Args:
            num: PF key number (1-24)
        """
        if num < 1 or num > 24:
            raise ValueError(f"PF key must be 1-24, got {num}")

        pf_methods = {
            1: self._tnz.pf1,
            2: self._tnz.pf2,
            3: self._tnz.pf3,
            4: self._tnz.pf4,
            5: self._tnz.pf5,
            6: self._tnz.pf6,
            7: self._tnz.pf7,
            8: self._tnz.pf8,
            9: self._tnz.pf9,
            10: self._tnz.pf10,
            11: self._tnz.pf11,
            12: self._tnz.pf12,
            13: self._tnz.pf13,
            14: self._tnz.pf14,
            15: self._tnz.pf15,
            16: self._tnz.pf16,
            17: self._tnz.pf17,
            18: self._tnz.pf18,
            19: self._tnz.pf19,
            20: self._tnz.pf20,
            21: self._tnz.pf21,
            22: self._tnz.pf22,
            23: self._tnz.pf23,
            24: self._tnz.pf24,
        }
        pf_methods[num]()

    def pa(self, num: int) -> None:
        """
        Send a PA (Program Attention) key.

        Args:
            num: PA key number (1-3)
        """
        if num < 1 or num > 3:
            raise ValueError(f"PA key must be 1-3, got {num}")

        pa_methods = {
            1: self._tnz.pa1,
            2: self._tnz.pa2,
            3: self._tnz.pa3,
        }
        pa_methods[num]()

    def attn(self) -> None:
        """Send ATTN (Attention) key."""
        self._tnz.attn()

    # =========================================================================
    # Wait / Sync Operations
    # =========================================================================

    def wait(self, timeout: float = 30.0) -> bool:
        """
        Wait for the host to respond (screen update).

        Args:
            timeout: Maximum seconds to wait (default: 30)

        Returns:
            True if screen was updated, False if timeout.
        """
        return bool(self._tnz.wait(timeout=timeout))

    def wait_for_text(
        self,
        text: str,
        timeout: float = 30.0,
        case_sensitive: bool = False,
    ) -> bool:
        """
        Wait for specific text to appear on screen.

        Args:
            text: Text to wait for
            timeout: Maximum seconds to wait (default: 30)
            case_sensitive: Whether the text match is case sensitive (default: False)
        Returns:
            True if text appeared, False if timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.screen_contains(text, case_sensitive):
                return True
            time.sleep(0.5)

        return False

    def wait_for_keyboard(self, timeout: float = 30.0) -> bool:
        """
        Wait for keyboard to become unlocked.

        Args:
            timeout: Maximum seconds to wait (default: 30)

        Returns:
            True if keyboard unlocked, False if timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            if not self.is_keyboard_locked:
                return True
            self.wait(timeout=0.1)

        return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def snapshot(self) -> dict:
        """
        Take a snapshot of the current screen state.

        Returns:
            Dictionary with screen content, fields, and cursor position.
        """
        return {
            "screen": self.screen,
            "cursor": {
                "row": self.cursor_row,
                "col": self.cursor_col,
                "address": self._tnz.curadd,
            },
            "fields": [
                {
                    "address": f.address,
                    "row": f.row,
                    "col": f.col,
                    "length": f.length,
                    "protected": f.protected,
                    "intensified": f.intensified,
                    "hidden": f.hidden,
                    "value": f.value,
                }
                for f in self.get_fields()
            ],
            "rows": self.rows,
            "cols": self.cols,
            "keyboard_locked": self.is_keyboard_locked,
        }

    def __repr__(self) -> str:
        return f"Host(rows={self.rows}, cols={self.cols}, cursor=({self.cursor_row}, {self.cursor_col}))"
