# ============================================================================
# TN3270 Messages
# ============================================================================

from typing import Literal

from pydantic import BaseModel

from .base import BaseMessage
from .types import MessageType


class TN3270Field(BaseModel):
    """Represents a 3270 field on the screen."""

    start: int  # Starting address (0-indexed linear position)
    end: int  # Ending address (exclusive)
    protected: bool  # True if field is protected (no input allowed)
    intensified: bool  # True if field is intensified
    row: int  # Starting row (0-indexed)
    col: int  # Starting column (0-indexed)
    length: int  # Field length in characters


class TN3270ScreenMeta(BaseModel):
    """Metadata for TN3270 screen message."""

    fields: list[TN3270Field]
    cursorRow: int  # Current cursor row (0-indexed)
    cursorCol: int  # Current cursor column (0-indexed)
    rows: int  # Screen rows
    cols: int  # Screen columns


class TN3270ScreenMessage(BaseMessage):
    """TN3270 screen update with field information."""

    type: Literal[MessageType.TN3270_SCREEN] = MessageType.TN3270_SCREEN
    meta: TN3270ScreenMeta


class TN3270CursorMeta(BaseModel):
    """Metadata for TN3270 cursor message."""

    row: int  # Cursor row (0-indexed)
    col: int  # Cursor column (0-indexed)


class TN3270CursorMessage(BaseMessage):
    """TN3270 cursor position update."""

    type: Literal[MessageType.TN3270_CURSOR] = MessageType.TN3270_CURSOR
    meta: TN3270CursorMeta


def create_tn3270_screen_message(
    session_id: str,
    ansi_data: str,
    fields: list[TN3270Field],
    cursor_row: int,
    cursor_col: int,
    rows: int,
    cols: int,
) -> TN3270ScreenMessage:
    """Create a TN3270 screen message."""
    return TN3270ScreenMessage(
        session_id=session_id,
        payload=ansi_data,
        meta=TN3270ScreenMeta(
            fields=fields,
            cursorRow=cursor_row,
            cursorCol=cursor_col,
            rows=rows,
            cols=cols,
        ),
    )


def create_tn3270_cursor_message(
    session_id: str,
    row: int,
    col: int,
) -> TN3270CursorMessage:
    """Create a TN3270 cursor position message."""
    return TN3270CursorMessage(
        session_id=session_id,
        payload="",
        meta=TN3270CursorMeta(row=row, col=col),
    )
