# ============================================================================
# Message Parser
# ============================================================================

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.models.ast import ASTItemResultMessage, ASTPausedMessage, ASTProgressMessage

from .types import MessageType

if TYPE_CHECKING:
    from .ast import ASTRunMessage, ASTControlMessage, ASTStatusMessage
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
    from .tn3270 import TN3270CursorMessage, TN3270ScreenMessage

    MessageEnvelope = (
        DataMessage
        | ResizeMessage
        | PingMessage
        | PongMessage
        | ErrorMessage
        | SessionCreateMessage
        | SessionDestroyMessage
        | SessionCreatedMessage
        | SessionDestroyedMessage
        | ASTRunMessage
        | ASTControlMessage
        | ASTStatusMessage
        | ASTPausedMessage
        | ASTProgressMessage
        | ASTItemResultMessage
        | TN3270ScreenMessage
        | TN3270CursorMessage
    )


def parse_message(raw: str | bytes) -> "MessageEnvelope":
    """Parse a raw JSON message into the appropriate message type."""
    # Import here to avoid circular imports
    from .ast import ASTRunMessage, ASTControlMessage, ASTStatusMessage
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

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    data = json.loads(raw)
    msg_type = data.get("type")

    match msg_type:
        case MessageType.DATA:
            return DataMessage.model_validate(data)
        case MessageType.RESIZE:
            return ResizeMessage.model_validate(data)
        case MessageType.PING:
            return PingMessage.model_validate(data)
        case MessageType.PONG:
            return PongMessage.model_validate(data)
        case MessageType.ERROR:
            return ErrorMessage.model_validate(data)
        case MessageType.SESSION_CREATE:
            return SessionCreateMessage.model_validate(data)
        case MessageType.SESSION_DESTROY:
            return SessionDestroyMessage.model_validate(data)
        case MessageType.SESSION_CREATED:
            return SessionCreatedMessage.model_validate(data)
        case MessageType.SESSION_DESTROYED:
            return SessionDestroyedMessage.model_validate(data)
        case MessageType.AST_RUN:
            return ASTRunMessage.model_validate(data)
        case MessageType.AST_CONTROL:
            return ASTControlMessage.model_validate(data)
        case MessageType.AST_STATUS:
            return ASTStatusMessage.model_validate(data)
        case _:
            raise ValueError(f"Unknown message type: {msg_type}")


def serialize_message(msg: "MessageEnvelope") -> str:
    """Serialize a message to JSON."""
    return msg.model_dump_json(by_alias=True)
