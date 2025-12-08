# ============================================================================
# AST (Automated Streamlined Transaction) Message Models
# ============================================================================

from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict

from .base import BaseMessage
from .types import MessageType


# ============================================================================
# AST Run
# ============================================================================


class ASTRunMeta(BaseModel):
    """AST run metadata."""

    model_config = ConfigDict(populate_by_name=True)

    ast_name: str = Field(alias="astName")
    """Name of the AST to run."""

    params: dict[str, Any] | None = None
    """Optional parameters for the AST."""

class ASTRunMessage(BaseMessage):
    """Request to run an AST."""

    type: Literal["ast.run"] = "ast.run"
    meta: ASTRunMeta


# ============================================================================
# AST Control (Pause/Resume/Cancel)
# ============================================================================


class ASTControlMeta(BaseModel):
    """AST control command metadata."""

    model_config = ConfigDict(populate_by_name=True)

    action: Literal["pause", "resume", "cancel"]
    """Control action to perform."""


class ASTControlMessage(BaseMessage):
    """Request to control a running AST (pause/resume/cancel)."""

    type: Literal["ast.control"] = "ast.control"
    meta: ASTControlMeta


# ============================================================================
# AST Paused Status
# ============================================================================


class ASTPausedMeta(BaseModel):
    """AST paused status metadata."""

    model_config = ConfigDict(populate_by_name=True)

    paused: bool
    """Whether the AST is currently paused."""

    message: str | None = None
    """Optional message."""

class ASTPausedMessage(BaseMessage):
    """AST paused status update."""

    type: Literal["ast.paused"] = "ast.paused"
    meta: ASTPausedMeta


# ============================================================================
# AST Status
# ============================================================================


class ASTStatusMeta(BaseModel):
    """AST status metadata."""

    model_config = ConfigDict(populate_by_name=True)

    ast_name: str = Field(alias="astName")
    """Name of the AST."""

    status: Literal["pending", "running", "success", "failed", "timeout", "cancelled"]
    """Current status of the AST."""

    message: str | None = None
    """Optional status message."""

    error: str | None = None
    """Error details if failed."""

    duration: float | None = None
    """Execution duration in seconds."""

    data: dict[str, Any] | None = None
    """Additional data from the AST."""

class ASTStatusMessage(BaseMessage):
    """AST execution status update."""

    type: Literal["ast.status"] = "ast.status"
    meta: ASTStatusMeta


# ============================================================================
# AST Progress
# ============================================================================


class ASTProgressMeta(BaseModel):
    """AST progress metadata."""

    model_config = ConfigDict(populate_by_name=True)

    execution_id: str = Field(alias="executionId")
    """Execution ID."""

    ast_name: str = Field(alias="astName")
    """Name of the AST."""

    current: int
    """Current item being processed (1-based)."""

    total: int
    """Total items to process."""

    percent: int
    """Progress percentage (0-100)."""

    current_item: str | None = Field(default=None, alias="currentItem")
    """Current item identifier (e.g., policy number)."""

    item_status: (
        Literal["pending", "running", "success", "failed", "skipped"] | None
    ) = Field(default=None, alias="itemStatus")
    """Status of current item."""

    message: str | None = None
    """Message about current progress."""

class ASTProgressMessage(BaseMessage):
    """AST execution progress update."""

    type: Literal["ast.progress"] = "ast.progress"
    meta: ASTProgressMeta


# ============================================================================
# AST Item Result
# ============================================================================


class ASTItemResultMeta(BaseModel):
    """AST item result metadata."""

    model_config = ConfigDict(populate_by_name=True)

    execution_id: str = Field(alias="executionId")
    """Execution ID."""

    item_id: str = Field(alias="itemId")
    """Item identifier (e.g., policy number)."""

    status: Literal["success", "failed", "skipped"]
    """Item status."""

    duration_ms: int | None = Field(default=None, alias="durationMs")
    """Duration in milliseconds."""

    error: str | None = None
    """Error message if failed."""

    data: dict[str, Any] | None = None
    """Additional data."""

class ASTItemResultMessage(BaseMessage):
    """AST item processing result."""

    type: Literal["ast.item_result"] = "ast.item_result"
    meta: ASTItemResultMeta


# ============================================================================
# Factory Functions
# ============================================================================


def create_ast_status_message(
    session_id: str,
    ast_name: str,
    status: Literal["pending", "running", "success", "failed", "timeout", "cancelled"],
    message: str | None = None,
    error: str | None = None,
    duration: float | None = None,
    data: dict[str, Any] | None = None,
) -> ASTStatusMessage:
    """Create an AST status message."""
    return ASTStatusMessage(
        sessionId=session_id,
        payload=message or "",
        meta=ASTStatusMeta(
            astName=ast_name,
            status=status,
            message=message,
            error=error,
            duration=duration,
            data=data,
        ),
    )


def create_ast_progress_message(
    session_id: str,
    execution_id: str,
    ast_name: str,
    current: int,
    total: int,
    current_item: str | None = None,
    item_status: (
        Literal["pending", "running", "success", "failed", "skipped"] | None
    ) = None,
    message: str | None = None,
) -> ASTProgressMessage:
    """Create an AST progress message."""
    percent = round((current / total) * 100) if total > 0 else 0
    return ASTProgressMessage(
        sessionId=session_id,
        payload=message or f"Processing {current}/{total}",
        meta=ASTProgressMeta(
            executionId=execution_id,
            astName=ast_name,
            current=current,
            total=total,
            percent=percent,
            currentItem=current_item,
            itemStatus=item_status,
            message=message,
        ),
    )


def create_ast_item_result_message(
    session_id: str,
    execution_id: str,
    item_id: str,
    status: Literal["success", "failed", "skipped"],
    duration_ms: int | None = None,
    error: str | None = None,
    data: dict[str, Any] | None = None,
) -> ASTItemResultMessage:
    """Create an AST item result message."""
    return ASTItemResultMessage(
        sessionId=session_id,
        payload=item_id,
        meta=ASTItemResultMeta(
            executionId=execution_id,
            itemId=item_id,
            status=status,
            durationMs=duration_ms,
            error=error,
            data=data,
        ),
    )


def create_ast_paused_message(
    session_id: str,
    paused: bool,
    message: str | None = None,
) -> ASTPausedMessage:
    """Create an AST paused status message."""
    return ASTPausedMessage(
        sessionId=session_id,
        payload=message or ("Paused" if paused else "Resumed"),
        meta=ASTPausedMeta(
            paused=paused,
            message=message,
        ),
    )
