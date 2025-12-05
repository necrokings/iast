# ============================================================================
# Data Message
# ============================================================================

from typing import Any, Literal

from .base import BaseMessage
from .types import MessageType


class DataMessage(BaseMessage):
    """Terminal data (input/output)."""

    type: Literal[MessageType.DATA] = MessageType.DATA
    meta: dict[str, Any] | None = None


def create_data_message(session_id: str, data: str) -> DataMessage:
    """Create a data message."""
    return DataMessage(sessionId=session_id, payload=data)
