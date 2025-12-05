# ============================================================================
# Error Message
# ============================================================================

from typing import Any, Literal

from pydantic import BaseModel

from .base import BaseMessage
from .types import MessageType


class ErrorMeta(BaseModel):
    """Error metadata."""

    code: str
    details: dict[str, Any] | None = None


class ErrorMessage(BaseMessage):
    """Error response."""

    type: Literal[MessageType.ERROR] = MessageType.ERROR
    meta: ErrorMeta


def create_error_message(session_id: str, code: str, message: str) -> ErrorMessage:
    """Create an error message."""
    return ErrorMessage(
        sessionId=session_id,
        payload=message,
        meta=ErrorMeta(code=code),
    )
