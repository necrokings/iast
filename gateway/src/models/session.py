# ============================================================================
# Session Messages
# ============================================================================

from typing import Any, Literal

from pydantic import BaseModel, Field

from .base import BaseMessage
from .types import MessageType


# ----------------------------------------------------------------------------
# Session Create
# ----------------------------------------------------------------------------


class SessionCreateMeta(BaseModel):
    """Session create metadata."""

    shell: str | None = None
    cols: int | None = None
    rows: int | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None


class SessionCreateMessage(BaseMessage):
    """Request to create a TN3270 session."""

    type: Literal[MessageType.SESSION_CREATE] = MessageType.SESSION_CREATE
    meta: SessionCreateMeta | None = None


# ----------------------------------------------------------------------------
# Session Destroy
# ----------------------------------------------------------------------------


class SessionDestroyMessage(BaseMessage):
    """Request to destroy a TN3270 session."""

    type: Literal[MessageType.SESSION_DESTROY] = MessageType.SESSION_DESTROY
    meta: dict[str, Any] | None = None


# ----------------------------------------------------------------------------
# Session Created
# ----------------------------------------------------------------------------


class SessionCreatedMeta(BaseModel):
    """Session created metadata."""

    shell: str
    pid: int | None = None


class SessionCreatedMessage(BaseMessage):
    """TN3270 session created confirmation."""

    type: Literal[MessageType.SESSION_CREATED] = MessageType.SESSION_CREATED
    meta: SessionCreatedMeta


def create_session_created_message(
    session_id: str, shell: str, pid: int
) -> SessionCreatedMessage:
    """Create a session created message."""
    return SessionCreatedMessage(
        sessionId=session_id,
        meta=SessionCreatedMeta(shell=shell, pid=pid),
    )


# ----------------------------------------------------------------------------
# Session Destroyed
# ----------------------------------------------------------------------------


class SessionDestroyedMeta(BaseModel):
    """Session destroyed metadata."""

    exit_code: int | None = Field(default=None, alias="exitCode")
    signal: str | None = None

    model_config = {"populate_by_name": True}


class SessionDestroyedMessage(BaseMessage):
    """TN3270 session destroyed confirmation."""

    type: Literal[MessageType.SESSION_DESTROYED] = MessageType.SESSION_DESTROYED
    meta: SessionDestroyedMeta | None = None


def create_session_destroyed_message(
    session_id: str, reason: str
) -> SessionDestroyedMessage:
    """Create a session destroyed message."""
    return SessionDestroyedMessage(
        sessionId=session_id,
        payload=reason,
        meta=SessionDestroyedMeta(),
    )
