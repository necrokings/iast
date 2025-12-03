# ============================================================================
# Message Types
# ============================================================================

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .data import DataMessage
    from .error import ErrorMessage
    from .ping import PingMessage, PongMessage
    from .resize import ResizeMessage
    from .session import (
        SessionCreatedMessage,
        SessionCreateMessage,
        SessionDestroyedMessage,
        SessionDestroyMessage,
    )
    from .tn3270 import TN3270ScreenMessage, TN3270CursorMessage


class MessageType(StrEnum):
    """Message types matching the TypeScript shared package."""

    DATA = "data"
    RESIZE = "resize"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    SESSION_CREATE = "session.create"
    SESSION_DESTROY = "session.destroy"
    SESSION_CREATED = "session.created"
    SESSION_DESTROYED = "session.destroyed"
    TN3270_SCREEN = "tn3270.screen"
    TN3270_CURSOR = "tn3270.cursor"


# Type alias for all message types
MessageEnvelope = (
    "DataMessage"
    "| ResizeMessage"
    "| PingMessage"
    "| PongMessage"
    "| ErrorMessage"
    "| SessionCreateMessage"
    "| SessionDestroyMessage"
    "| SessionCreatedMessage"
    "| SessionDestroyedMessage"
    "| TN3270ScreenMessage"
    "| TN3270CursorMessage"
)
