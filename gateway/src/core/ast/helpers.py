# ============================================================================
# AST Execution Helpers
# ============================================================================
"""
Helper functions for AST execution workflows.

These helpers are used by both sequential and parallel execution methods
to reduce code duplication.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Optional

import structlog

from .result import ASTResult, ASTStatus, ItemResult

if TYPE_CHECKING:
    from .base import AST
    from ...services.tn3270.host import Host

log = structlog.get_logger()


def validate_credentials(
    ast: "AST", **kwargs: Any
) -> tuple[str | None, str | None, str, str, list[Any]]:
    """Extract and return execution parameters from kwargs.
    
    Args:
        ast: The AST instance
        **kwargs: Execution parameters
        
    Returns:
        Tuple of (username, password, app_user_id, session_id, raw_items)
    """
    from uuid import uuid4
    
    username = kwargs.get("username")
    password = kwargs.get("password")
    app_user_id: str = kwargs.get("userId", "anonymous")
    raw_items: list[Any] = ast.prepare_items(**kwargs)
    
    # Set execution and session IDs
    ast._execution_id = kwargs.get("execution_id") or str(uuid4())
    ast._session_id = kwargs.get("sessionId", ast._execution_id)
    
    return username, password, app_user_id, ast._session_id, raw_items


def create_credentials_error_result() -> ASTResult:
    """Create an error result for missing credentials."""
    return ASTResult(
        status=ASTStatus.FAILED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
        message="Missing required parameters: username and password are required",
        error="ValidationError: username and password must be provided",
    )


def create_initial_result(username: str, item_count: int) -> ASTResult:
    """Create the initial running ASTResult."""
    return ASTResult(
        status=ASTStatus.RUNNING,
        started_at=datetime.now(),
        data={"username": username, "policyCount": item_count},
    )


def initialize_execution(
    ast: "AST",
    username: str,
    app_user_id: str,
    item_count: int,
    started_at: datetime,
) -> None:
    """Initialize DB and create execution record."""
    ast._init_db()
    ast._create_execution_record(username, app_user_id, item_count, started_at)


def finalize_result(
    ast: "AST",
    result: ASTResult,
    item_results: list[ItemResult],
    total: int,
    username: str,
    is_parallel: bool = False,
) -> None:
    """Finalize result with counts and update execution record."""
    success_count = sum(1 for r in item_results if r.status == "success")
    failed_count = sum(1 for r in item_results if r.status == "failed")
    skipped_count = sum(1 for r in item_results if r.status == "skipped")

    result.item_results = item_results
    result.data.update(
        {
            "successCount": success_count,
            "failedCount": failed_count,
            "skippedCount": skipped_count,
        }
    )

    mode_suffix = " (parallel)" if is_parallel else ""
    
    if ast._cancelled:
        processed = len(item_results)
        result.status = ASTStatus.CANCELLED
        result.message = f"Cancelled by user. Processed {processed}/{total} items."
        ast._update_execution_record("cancelled", result.message, item_results)
        log.info(f"AST cancelled{mode_suffix}", username=username)
    else:
        mode_text = "in parallel " if is_parallel else ""
        result.status = ASTStatus.SUCCESS
        result.message = (
            f"Processed {total} items {mode_text}"
            f"({success_count} success, {failed_count} failed, {skipped_count} skipped)"
        )
        ast._update_execution_record("success", result.message, item_results)
        log.info(f"AST completed successfully{mode_suffix}", username=username)


def handle_execution_error(
    ast: "AST",
    result: ASTResult,
    item_results: list[ItemResult],
    error: Exception,
    username: str,
    host: Optional["Host"] = None,
) -> None:
    """Handle execution error and update records."""
    result.status = ASTStatus.FAILED
    result.error = str(error)
    result.message = f"Error during execution: {error}"
    result.item_results = item_results

    if host:
        try:
            host.show_screen("Error State")
        except Exception:
            pass

    ast._update_execution_record(
        "failed", result.message, item_results, error=str(error)
    )
    log.exception("AST failed", username=username)


def record_item_result(
    ast: "AST",
    item_id: str,
    status: Literal["success", "failed", "skipped"],
    item_start: datetime,
    item_results: list[ItemResult],
    current: int,
    total: int,
    error: Optional[str] = None,
    item_data: Optional[dict] = None,
) -> int:
    """Record an item result, report, and persist.
    
    Returns:
        Duration in milliseconds
    """
    item_end = datetime.now()
    duration_ms = int((item_end - item_start).total_seconds() * 1000)

    item_result = ItemResult(
        item_id=item_id,
        status=status,
        started_at=item_start,
        completed_at=item_end,
        duration_ms=duration_ms,
        error=error,
        data=item_data or {},
    )
    item_results.append(item_result)

    ast.report_item_result(
        item_id=item_id,
        status=status,
        duration_ms=duration_ms,
        error=error,
        data=item_data,
    )

    ast._save_item_result(
        item_id=item_id,
        status=status,
        duration_ms=duration_ms,
        started_at=item_start,
        completed_at=item_end,
        error=error,
        item_data=item_data,
    )

    message = f"Item {current}/{total}: "
    if status == "success":
        message += "Completed"
    elif status == "failed":
        message += f"Failed - {error}"
    else:
        message += "Skipped"

    ast.report_progress(
        current=current,
        total=total,
        current_item=item_id,
        item_status=status,
        message=message,
    )

    return duration_ms


def process_single_item_workflow(
    ast: "AST",
    host: "Host",
    item: Any,
    index: int,
    total: int,
    username: str,
    password: str,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Execute the authenticate -> process -> logoff workflow for a single item.
    
    Returns:
        Tuple of (success, error, item_data)
    """
    # Authenticate
    success, error = ast.authenticate(
        host,
        user=username,
        password=password,
        expected_keywords_after_login=ast.auth_expected_keywords,
        application=ast.auth_application,
        group=ast.auth_group,
    )
    if not success:
        return False, f"Login failed: {error}", None

    # Process
    success, error, item_data = ast.process_single_item(host, item, index, total)
    if not success:
        return False, f"Process failed: {error}", None

    # Logoff
    success, error = ast.logoff(host)
    if not success:
        # Log warning but don't fail the item if logoff fails
        log.warning("Logoff failed", item=ast.get_item_id(item), error=error)

    return True, None, item_data
