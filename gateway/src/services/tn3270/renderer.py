# ============================================================================
# TN3270 Screen Renderer - Converts 3270 screen to ANSI escape sequences
# ============================================================================
"""
Renders 3270 screen data to ANSI escape sequences for xterm.js display.

The 3270 terminal has:
- Fixed screen positions (not scrolling)
- Field attributes (protected, highlighted, colors)
- Cursor positioning
- Special characters (field markers, etc.)

This renderer converts the 3270 screen buffer to ANSI sequences that
xterm.js can display properly.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tnz.tnz import Tnz


# EBCDIC to ASCII translation for display
# Field attribute characters are not displayed

# 3270 color codes to ANSI color codes
COLOR_MAP = {
    0x00: 0,  # Default
    0xF0: 0,  # Default (neutral/black)
    0xF1: 4,  # Blue
    0xF2: 1,  # Red
    0xF3: 5,  # Pink/Magenta
    0xF4: 2,  # Green
    0xF5: 6,  # Turquoise/Cyan
    0xF6: 3,  # Yellow
    0xF7: 7,  # White (neutral/white)
}

# Extended highlighting
HIGHLIGHT_BLINK = 0xF1
HIGHLIGHT_REVERSE = 0xF2
HIGHLIGHT_UNDERSCORE = 0xF4


@dataclass
class ScreenCell:
    """Represents a single cell on the 3270 screen."""

    char: str
    fg_color: int = 0
    bg_color: int = 0
    highlight: int = 0
    is_field_attr: bool = False
    is_protected: bool = False
    is_intensified: bool = False


@dataclass
class Field:
    """Represents a 3270 field."""

    start: int  # Starting address (inclusive)
    end: int  # Ending address (exclusive, or next field start)
    protected: bool  # True if protected (no input allowed)
    intensified: bool  # True if intensified display
    row: int  # Starting row (0-indexed)
    col: int  # Starting column (0-indexed)
    length: int  # Field length in characters


@dataclass
class ScreenData:
    """Complete screen data including field map."""

    ansi: str  # ANSI escape sequence for display
    fields: list[Field]  # Field definitions
    cursor_row: int  # Current cursor row (0-indexed)
    cursor_col: int  # Current cursor column (0-indexed)
    rows: int  # Screen rows
    cols: int  # Screen columns


class TN3270Renderer:
    """Renders 3270 screen to ANSI escape sequences."""

    def __init__(self) -> None:
        self._last_fg = -1
        self._last_bg = -1
        self._last_highlight = -1

    def render_screen(self, tnz: "Tnz") -> str:
        """
        Render the entire 3270 screen to ANSI escape sequences.

        Returns a string with ANSI escape codes that can be sent to xterm.js.
        """
        screen_data = self.render_screen_with_fields(tnz)
        return screen_data.ansi

    def render_screen_with_fields(self, tnz: "Tnz") -> ScreenData:
        """
        Render the 3270 screen and extract field information.

        Returns ScreenData with both ANSI output and field map.
        """
        output: list[str] = []

        # Clear screen and move to home position
        output.append("\x1b[2J")  # Clear screen
        output.append("\x1b[H")  # Move to home (1,1)

        maxrow = tnz.maxrow
        maxcol = tnz.maxcol

        plane_dc = tnz.plane_dc
        plane_fa = tnz.plane_fa
        plane_fg = tnz.plane_fg
        plane_bg = tnz.plane_bg
        plane_eh = tnz.plane_eh

        # Track current attributes to minimize escape sequences
        current_fg = 7  # Default white
        current_bg = 0  # Default black
        current_highlight = 0

        # Field attribute state
        field_protected = False
        field_intensified = False
        field_fg = 0xF4  # Default green for unprotected

        # Field tracking
        fields: list[Field] = []
        field_starts: list[tuple[int, bool, bool]] = (
            []
        )  # (addr, protected, intensified)

        # First pass: find all field attribute positions
        for addr in range(maxrow * maxcol):
            fa = plane_fa[addr]
            if fa != 0:
                protected = bool(fa & 0x20)
                intensified = bool(fa & 0x08)
                field_starts.append((addr, protected, intensified))

        # Build fields from field attribute positions
        for i, (start_addr, protected, intensified) in enumerate(field_starts):
            # Field content starts one position after the field attribute
            content_start = start_addr + 1
            if content_start >= maxrow * maxcol:
                content_start = 0  # Wrap around

            # Find end (next field attribute or wrap to first)
            if i + 1 < len(field_starts):
                end_addr = field_starts[i + 1][0]
            else:
                # Last field wraps to first field attribute
                end_addr = field_starts[0][0] if field_starts else maxrow * maxcol

            # Calculate length (handle wrap-around)
            if end_addr > content_start:
                length = end_addr - content_start
            else:
                length = (maxrow * maxcol - content_start) + end_addr

            row = content_start // maxcol
            col = content_start % maxcol

            fields.append(
                Field(
                    start=content_start,
                    end=end_addr,
                    protected=protected,
                    intensified=intensified,
                    row=row,
                    col=col,
                    length=length,
                )
            )

        # Render screen
        for row in range(maxrow):
            if row > 0:
                output.append("\r\n")

            for col in range(maxcol):
                addr = row * maxcol + col

                fa = plane_fa[addr]
                dc = plane_dc[addr]
                fg = plane_fg[addr]
                bg = plane_bg[addr]
                eh = plane_eh[addr]

                # Check if this is a field attribute position
                if fa != 0:
                    # Field attribute - decode it
                    field_protected = bool(fa & 0x20)
                    field_intensified = bool(fa & 0x08)

                    # Field attributes are displayed as spaces
                    char = " "

                    # Determine field color based on attributes
                    if field_protected:
                        if field_intensified:
                            field_fg = 0xF7  # White - intensified protected
                        else:
                            field_fg = 0xF1  # Blue - protected
                    else:
                        if field_intensified:
                            field_fg = 0xF7  # White - intensified input
                        else:
                            field_fg = 0xF4  # Green - normal input
                else:
                    # Regular character
                    # Decode EBCDIC to displayable character
                    char = self._decode_char(dc, tnz)

                # Determine colors
                # If explicit color set, use it; otherwise use field default
                if fg != 0:
                    cell_fg = COLOR_MAP.get(fg, 7)
                else:
                    cell_fg = COLOR_MAP.get(field_fg, 2)  # Default green

                if bg != 0:
                    cell_bg = COLOR_MAP.get(bg, 0)
                else:
                    cell_bg = 0  # Default black background

                # Build escape sequence if attributes changed
                if (
                    cell_fg != current_fg
                    or cell_bg != current_bg
                    or eh != current_highlight
                ):
                    seq = self._build_attr_sequence(cell_fg, cell_bg, eh)
                    output.append(seq)
                    current_fg = cell_fg
                    current_bg = cell_bg
                    current_highlight = eh

                output.append(char)

        # Reset attributes
        output.append("\x1b[0m")

        # Position cursor
        cursor_row = tnz.curadd // maxcol
        cursor_col = tnz.curadd % maxcol
        output.append(f"\x1b[{cursor_row + 1};{cursor_col + 1}H")

        return ScreenData(
            ansi="".join(output),
            fields=fields,
            cursor_row=cursor_row,
            cursor_col=cursor_col,
            rows=maxrow,
            cols=maxcol,
        )

    def render_diff(self, tnz: "Tnz", prev_screen: bytes | None = None) -> str:
        """
        Render only the changes since the last screen.

        For now, just re-render the full screen. Could be optimized
        to only send changed regions.
        """
        return self.render_screen(tnz)

    def _decode_char(self, dc: int, tnz: "Tnz") -> str:
        """Decode an EBCDIC character to displayable ASCII/Unicode."""
        if dc == 0 or dc == 0x00:
            return " "  # Null displays as space

        if dc == 0x40:
            return " "  # EBCDIC space

        try:
            # Use tnz's codec to decode
            codec_info = tnz.codec_info.get(0)
            if codec_info:
                decoded, _ = codec_info.decode(bytes([dc]))
                if decoded and decoded.isprintable():
                    return decoded
                return " "

            # Fallback: try cp037 (common EBCDIC)
            decoded = bytes([dc]).decode("cp037", errors="replace")
            if decoded.isprintable():
                return decoded
            return " "
        except Exception:
            return " "

    def _build_attr_sequence(self, fg: int, bg: int, highlight: int) -> str:
        """Build ANSI SGR (Select Graphic Rendition) sequence."""
        parts: list[str] = []

        # Reset first to clear previous attributes
        parts.append("0")

        # Foreground color (30-37 for standard colors)
        if fg >= 0:
            parts.append(str(30 + fg))

        # Background color (40-47 for standard colors)
        if bg > 0:
            parts.append(str(40 + bg))

        # Highlighting
        if highlight == HIGHLIGHT_BLINK:
            parts.append("5")  # Blink
        elif highlight == HIGHLIGHT_REVERSE:
            parts.append("7")  # Reverse video
        elif highlight == HIGHLIGHT_UNDERSCORE:
            parts.append("4")  # Underscore

        return f"\x1b[{';'.join(parts)}m"

    def get_cursor_position(self, tnz: "Tnz") -> tuple[int, int]:
        """Get cursor position as (row, col) 0-indexed."""
        row = tnz.curadd // tnz.maxcol
        col = tnz.curadd % tnz.maxcol
        return row, col

    def get_screen_size(self, tnz: "Tnz") -> tuple[int, int]:
        """Get screen size as (rows, cols)."""
        return tnz.maxrow, tnz.maxcol

    def is_position_protected(self, tnz: "Tnz", row: int, col: int) -> bool:
        """Check if a screen position is in a protected field."""
        screen_data = self.render_screen_with_fields(tnz)
        addr = row * screen_data.cols + col

        for field in screen_data.fields:
            # Check if address is within this field
            if field.end > field.start:
                # Normal case - no wrap
                if field.start <= addr < field.end:
                    return field.protected
            else:
                # Wrap-around case
                if addr >= field.start or addr < field.end:
                    return field.protected

        # If no field contains this position, consider it protected
        # (positions before the first field attribute are protected)
        return True
