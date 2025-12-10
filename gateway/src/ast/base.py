# ============================================================================
# AST Base Class
# ============================================================================
"""
Base class for all AST (Automated Streamlined Transaction) scripts.
"""

import concurrent.futures
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional
from uuid import uuid4

import structlog

from ..db import get_dynamodb_client

if TYPE_CHECKING:
    from ..db import DynamoDBClient
    from ..services.tn3270.host import Host
    from tnz.ati import Ati

log = structlog.get_logger()


class ASTStatus(Enum):
    """Status of an AST execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ItemResult:
    """Result of processing a single item (e.g., policy)."""

    item_id: str
    status: Literal["success", "failed", "skipped"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ASTResult:
    """Result of an AST execution."""

    status: ASTStatus
    message: str = ""
    current_screen: str = ""
    data: dict[str, Any] = field(default_factory=lambda: {})
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    screenshots: list[str] = field(default_factory=lambda: [])
    item_results: list[ItemResult] = field(default_factory=lambda: [])

    @property
    def duration(self) -> float | None:
        """Get execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ASTStatus.SUCCESS


# Type for progress callback
ProgressCallback = Callable[
    [
        int,
        int,
        str | None,
        Literal["pending", "running", "success", "failed", "skipped"] | None,
        str | None,
    ],
    None,
]

# Type for item result callback
ItemResultCallback = Callable[
    [
        str,
        Literal["success", "failed", "skipped"],
        int | None,
        str | None,
        dict[str, Any] | None,
    ],
    None,
]

# Type for pause state callback
PauseStateCallback = Callable[[bool, str | None], None]


class AST(ABC):
    """
    Base class for Automated Streamlined Transaction scripts.

    Subclasses must implement the `execute` method with the specific
    automation logic.

    Example:
        class MyAST(AST):
            name = "my_ast"
            description = "Does something cool"

            def execute(self, host: Host, **kwargs) -> ASTResult:
                # Automation logic here
                return ASTResult(status=ASTStatus.SUCCESS)
    """

    name: str = "base"
    description: str = "Base AST class"

    # Authentication configuration - subclasses should override these
    auth_expected_keywords: list[str] = []  # Keywords to verify successful login
    auth_application: str = ""  # Application name for login
    auth_group: str = ""  # Group name for login

    def __init__(self) -> None:
        self._result: ASTResult | None = None
        self._execution_id: str = ""
        self._on_progress: ProgressCallback | None = None
        self._on_item_result: ItemResultCallback | None = None
        self._on_pause_state: PauseStateCallback | None = None

        # Pause/resume synchronization
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default
        self._is_paused = False
        self._cancelled = False
        self._db: Optional["DynamoDBClient"] = None
        self._session_id: str = ""

    def set_callbacks(
        self,
        on_progress: ProgressCallback | None = None,
        on_item_result: ItemResultCallback | None = None,
        on_pause_state: PauseStateCallback | None = None,
    ) -> None:
        """Set callbacks for progress, item results, and pause state."""
        self._on_progress = on_progress
        self._on_item_result = on_item_result
        self._on_pause_state = on_pause_state

    def pause(self) -> None:
        """Pause the AST execution. Will pause before the next policy."""
        if not self._is_paused:
            self._is_paused = True
            self._pause_event.clear()
            log.info("AST paused", ast=self.name, execution_id=self._execution_id)
            if self._on_pause_state:
                self._on_pause_state(
                    True, "AST paused - you can make manual adjustments"
                )

    def resume(self) -> None:
        """Resume the AST execution."""
        if self._is_paused:
            self._is_paused = False
            self._pause_event.set()
            log.info("AST resumed", ast=self.name, execution_id=self._execution_id)
            if self._on_pause_state:
                self._on_pause_state(False, "AST resumed")

    def cancel(self) -> None:
        """Cancel the AST execution."""
        self._cancelled = True
        self._pause_event.set()  # Unblock if paused
        log.info("AST cancelled", ast=self.name, execution_id=self._execution_id)

    def wait_if_paused(self, timeout: float | None = None) -> bool:
        """
        Block if paused, waiting for resume or cancel.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if should continue, False if cancelled
        """
        if self._cancelled:
            return False

        # Wait for the pause event to be set (i.e., not paused)
        self._pause_event.wait(timeout=timeout)

        return not self._cancelled

    @property
    def is_paused(self) -> bool:
        """Check if the AST is currently paused."""
        return self._is_paused

    @property
    def is_cancelled(self) -> bool:
        """Check if the AST has been cancelled."""
        return self._cancelled

    def report_progress(
        self,
        current: int,
        total: int,
        current_item: str | None = None,
        item_status: (
            Literal["pending", "running", "success", "failed", "skipped"] | None
        ) = None,
        message: str | None = None,
    ) -> None:
        """Report progress to the callback."""
        if self._on_progress:
            self._on_progress(current, total, current_item, item_status, message)
        log.debug(
            "AST progress",
            ast=self.name,
            current=current,
            total=total,
            current_item=current_item,
            item_status=item_status,
        )

    def report_item_result(
        self,
        item_id: str,
        status: Literal["success", "failed", "skipped"],
        duration_ms: int | None = None,
        error: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Report an item result to the callback."""
        if self._on_item_result:
            self._on_item_result(item_id, status, duration_ms, error, data)
        log.debug(
            "AST item result",
            ast=self.name,
            item_id=item_id,
            status=status,
            duration_ms=duration_ms,
        )

    def run(
        self,
        host: "Host",
        execution_id: str | None = None,
        **kwargs: Any,
    ) -> ASTResult:
        """
        Run the AST script.

        Args:
            host: The Host automation interface
            execution_id: Optional execution ID (generated if not provided)
            **kwargs: Additional parameters for the AST

        Returns:
            ASTResult with execution status and data
        """
        self._execution_id = execution_id or str(uuid4())
        log.info(
            f"Starting AST: {self.name}",
            ast=self.name,
            execution_id=self._execution_id,
            kwargs=kwargs,
        )

        result = ASTResult(
            status=ASTStatus.RUNNING,
            started_at=datetime.now(),
        )

        try:
            result = self.execute(host, **kwargs)
            result.started_at = result.started_at or datetime.now()

            if result.status == ASTStatus.RUNNING:
                result.status = ASTStatus.SUCCESS

            log.info(
                f"AST completed: {self.name}",
                ast=self.name,
                execution_id=self._execution_id,
                status=result.status.value,
                duration=result.duration,
            )

        except TimeoutError as e:
            result.status = ASTStatus.TIMEOUT
            result.error = str(e)
            result.message = f"Timeout: {e}"
            log.warning(
                f"AST timeout: {self.name}",
                ast=self.name,
                execution_id=self._execution_id,
                error=str(e),
            )

        except Exception as e:
            result.status = ASTStatus.FAILED
            result.error = str(e)
            result.message = f"Error: {e}"
            log.exception(
                f"AST failed: {self.name}",
                ast=self.name,
                execution_id=self._execution_id,
            )

        finally:
            result.completed_at = datetime.now()

        self._result = result
        return result

    @property
    def execution_id(self) -> str:
        """Get the current execution ID."""
        return self._execution_id

    # ------------------------------------------------------------------ #
    # Persistence helpers
    # ------------------------------------------------------------------ #
    def _init_db(self) -> None:
        """Initialize DynamoDB client, required for persistence."""
        self._db = get_dynamodb_client()

    def _save_item_result(
        self,
        item_id: str,
        status: Literal["success", "failed", "skipped"],
        duration_ms: int,
        started_at: datetime,
        completed_at: datetime,
        error: Optional[str] = None,
        item_data: Optional[dict] = None,
    ) -> None:
        """Save an item result to DynamoDB."""
        if not self._db:
            return

        data: dict[str, Any] = {
            "status": status,
            "duration_ms": duration_ms,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "entity_type": "POLICY_RESULT",
        }
        if error:
            data["error"] = error
        if item_data:
            data["policy_data"] = item_data

        try:
            self._db.put_policy_result(
                execution_id=self._execution_id,
                policy_number=item_id,
                data=data,
            )
        except Exception as e:  # pragma: no cover - defensive logging
            log.warning("Failed to save item result", item=item_id, error=str(e))

    def _create_execution_record(
        self,
        username: str,
        user_id: str,
        item_count: int,
        started_at: datetime,
    ) -> None:
        """Create an execution record in DynamoDB."""
        if not self._db:
            return

        try:
            self._db.put_execution(
                session_id=self._session_id,
                execution_id=self._execution_id,
                data={
                    "ast_name": self.name,
                    "user_id": user_id,
                    "host_user": username,
                    "policy_count": item_count,
                    "status": "running",
                    "started_at": started_at.isoformat(),
                    "entity_type": "EXECUTION",
                },
            )
            log.info(
                "Created execution record",
                execution_id=self._execution_id,
                user_id=user_id,
            )
        except Exception as e:  # pragma: no cover - defensive logging
            log.warning("Failed to create execution record", error=str(e))

    def _update_execution_record(
        self,
        status: str,
        message: str,
        item_results: list[ItemResult],
        error: Optional[str] = None,
    ) -> None:
        """Update execution record with final status."""
        if not self._db:
            return

        try:
            updates: dict[str, Any] = {
                "status": status,
                "completed_at": datetime.now().isoformat(),
                "message": message,
            }

            if error:
                updates["error"] = error
            else:
                updates["success_count"] = sum(
                    1 for r in item_results if r.status == "success"
                )
                updates["failed_count"] = sum(
                    1 for r in item_results if r.status == "failed"
                )
                updates["skipped_count"] = sum(
                    1 for r in item_results if r.status == "skipped"
                )

            self._db.update_execution(
                session_id=self._session_id,
                execution_id=self._execution_id,
                updates=updates,
            )
            log.info(
                "Updated execution record",
                execution_id=self._execution_id,
                status=status,
            )
        except Exception as e:  # pragma: no cover - defensive logging
            log.warning("Failed to update execution record", error=str(e))

    # ------------------------------------------------------------------ #
    # Hooks for subclasses
    # ------------------------------------------------------------------ #
    def authenticate(
        self,
        host: "Host",
        user: str,
        password: str,
        expected_keywords_after_login: list[str],
        application: str = "",
        group: str = "",
    ) -> tuple[bool, str, list[str]]:
        """Authenticate to the mainframe system.

        Common authentication logic that can be used by all AST subclasses.
        Override this method if you need custom authentication logic.

        Args:
            host: Host automation interface
            user: Username
            password: Password
            expected_keywords_after_login: List of text strings to expect after successful login
            application: Application name (optional)
            group: Group name (optional)

        Returns:
            Tuple of (success, error_message, screenshots)
        """
        screenshots: list[str] = []

        # Check if already at expected post-login screen (already authenticated)
        if expected_keywords_after_login:
            for keyword in expected_keywords_after_login:
                if host.screen_contains(keyword):
                    log.info("Already at expected screen", keyword=keyword)
                    screenshots.append(host.show_screen("Already Authenticated"))
                    return True, "", screenshots

        # Perform authentication
        log.info("Starting authentication", user=user)

        try:
            # Fill userid field
            if not host.fill_field_by_label("Userid", user, case_sensitive=False):
                error_msg = "Failed to find Userid field"
                log.error(error_msg)
                screenshots.append(host.show_screen("Userid Field Not Found"))
                return False, error_msg, screenshots

            # Fill password field
            if not host.fill_field_by_label("Password", password, case_sensitive=False):
                error_msg = "Failed to find Password field"
                log.error(error_msg)
                screenshots.append(host.show_screen("Password Field Not Found"))
                return False, error_msg, screenshots

            # Fill application field if provided
            if application and not host.fill_field_by_label(
                "Application", application, case_sensitive=False
            ):
                log.warning("Failed to find Application field", application=application)

            # Fill group field if provided
            if group and not host.fill_field_by_label(
                "Group", group, case_sensitive=False
            ):
                log.warning("Failed to find Group field", group=group)

            # Submit login
            host.enter()

            # Verify we reached expected screen
            if expected_keywords_after_login:
                for keyword in expected_keywords_after_login:
                    if host.wait_for_text(keyword):
                        log.info("Authentication successful", keyword=keyword)
                        screenshots.append(
                            host.show_screen("Authentication Successful")
                        )
                        return True, "", screenshots

                error_msg = f"Authentication may have failed - expected keywords not found: {expected_keywords_after_login}"
                log.error(error_msg)
                screenshots.append(host.show_screen("Authentication Failed"))
                return False, error_msg, screenshots

            log.info("Authentication completed")
            screenshots.append(host.show_screen("Authentication Completed"))
            return True, "", screenshots

        except Exception as e:
            error_msg = f"Exception during authentication: {str(e)}"
            log.error("Exception during authentication", error=str(e), exc_info=True)
            screenshots.append(host.show_screen("Authentication Exception"))
            return False, error_msg, screenshots

    @abstractmethod
    def logoff(
        self, host: "Host", target_screen_keywords: list[str] | None = None
    ) -> tuple[bool, str, list[str]]:
        """Logoff flow implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement logoff method")

    def validate_item(self, item: Any) -> bool:
        """Override to validate an item.

        Args:
            item: The item to validate (can be str, dict, or any type)

        Returns:
            True if valid, False to skip this item
        """
        return True

    def get_item_id(self, item: Any) -> str:
        """Get a string identifier for an item (used for logging and recording).

        Override this if items are dicts or complex objects.

        Args:
            item: The item to get an ID for

        Returns:
            String identifier for the item
        """
        if isinstance(item, dict):
            # Try common key names for ID
            return str(
                item.get("id") or item.get("policyNumber") or item.get("name") or item
            )
        return str(item)

    def prepare_items(self, **kwargs: Any) -> list[Any]:
        """Prepare items to process.

        Override this method to fetch items from external sources (e.g., API, database).
        By default, returns items from kwargs['policyNumbers'] or kwargs['items'].

        Items can be any type (str, dict, etc.) - process_single_item should handle the type.

        Args:
            **kwargs: Parameters passed to execute()

        Returns:
            List of items to process (can be strings, dicts, or any type)
        """
        return kwargs.get("policyNumbers") or kwargs.get("items") or []

    @abstractmethod
    def process_single_item(
        self,
        host: "Host",
        item: Any,
        index: int,
        total: int,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Per-item processing implemented by subclasses.

        Args:
            host: Host automation interface
            item: The item to process (can be str, dict, or any type from prepare_items)
            index: Current item index (1-based)
            total: Total number of items

        Returns:
            Tuple of (success, error_message, item_data)
        """
        raise NotImplementedError(
            "Subclasses must implement process_single_item method"
        )

    # ------------------------------------------------------------------ #
    # Execution helpers
    # ------------------------------------------------------------------ #
    def _record_item_result(
        self,
        item_id: str,
        status: Literal["success", "failed", "skipped"],
        item_start: datetime,
        item_results: list[ItemResult],
        current: int,
        total: int,
        error: Optional[str] = None,
        item_data: Optional[dict] = None,
    ) -> int:
        """Record an item result, report, and persist."""
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

        self.report_item_result(
            item_id=item_id,
            status=status,
            duration_ms=duration_ms,
            error=error,
            data=item_data,
        )

        self._save_item_result(
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

        self.report_progress(
            current=current,
            total=total,
            current_item=item_id,
            item_status=status,
            message=message,
        )

        return duration_ms

    # ------------------------------------------------------------------ #
    # Execute
    # ------------------------------------------------------------------ #
    def execute(self, host: "Host", **kwargs: Any) -> ASTResult:
        """
        Default execute implementation: login, process each item, logoff.
        Subclasses may override, but typically only implement process_single_item/logoff.
        """
        username = kwargs.get("username")
        password = kwargs.get("password")
        raw_items: list[Any] = self.prepare_items(**kwargs)
        app_user_id: str = kwargs.get("userId", "anonymous")
        self._session_id = kwargs.get("sessionId", self._execution_id)

        if not username or not password:
            return ASTResult(
                status=ASTStatus.FAILED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                message="Missing required parameters: username and password are required",
                error="ValidationError: username and password must be provided",
            )

        result = ASTResult(
            status=ASTStatus.RUNNING,
            started_at=datetime.now(),
            data={"username": username, "policyCount": len(raw_items)},
        )

        all_screenshots: list[str] = []
        item_results: list[ItemResult] = []

        self._init_db()
        self._create_execution_record(
            username,
            app_user_id,
            len(raw_items),
            result.started_at or datetime.now(),
        )

        try:
            if not raw_items:
                log.info("No items to process, returning early")
                result.status = ASTStatus.SUCCESS
                result.message = "No items to process"
                return result

            total = len(raw_items)
            log.info(f"Processing {total} items (full cycle each)...")

            for idx, item in enumerate(raw_items):
                if not self.wait_if_paused():
                    log.info("AST cancelled by user")
                    result.status = ASTStatus.CANCELLED
                    result.message = "Cancelled by user"
                    break

                item_id = self.get_item_id(item)
                item_start = datetime.now()
                self.report_progress(
                    current=idx + 1,
                    total=total,
                    current_item=item_id,
                    item_status="running",
                    message=f"Item {idx + 1}/{total}: Logging in",
                )

                if not self.validate_item(item):
                    self._record_item_result(
                        item_id=item_id,
                        status="skipped",
                        item_start=item_start,
                        item_results=item_results,
                        current=idx + 1,
                        total=total,
                        error="Invalid item",
                    )
                    continue

                try:
                    success, error, screenshots = self.authenticate(
                        host,
                        user=username,
                        password=password,
                        expected_keywords_after_login=self.auth_expected_keywords,
                        application=self.auth_application,
                        group=self.auth_group,
                    )
                    all_screenshots.extend(screenshots)
                    if not success:
                        raise Exception(f"Login failed: {error}")

                    self.report_progress(
                        current=idx + 1,
                        total=total,
                        current_item=item_id,
                        item_status="running",
                        message=f"Item {idx + 1}/{total}: Processing",
                    )
                    success, error, item_data = self.process_single_item(
                        host, item, idx + 1, total
                    )
                    if not success:
                        raise Exception(f"Process failed: {error}")

                    self.report_progress(
                        current=idx + 1,
                        total=total,
                        current_item=item_id,
                        item_status="running",
                        message=f"Item {idx + 1}/{total}: Logging off",
                    )
                    success, error, screenshots = self.logoff(host)
                    all_screenshots.extend(screenshots)
                    if not success:
                        raise Exception(f"Logoff failed: {error}")

                    duration_ms = self._record_item_result(
                        item_id=item_id,
                        status="success",
                        item_start=item_start,
                        item_results=item_results,
                        current=idx + 1,
                        total=total,
                        item_data=item_data,
                    )
                    log.info(
                        "Item completed successfully",
                        item=item_id,
                        duration_ms=duration_ms,
                    )

                except Exception as e:
                    error_screen = None
                    try:
                        error_screen = host.get_formatted_screen(show_row_numbers=False)
                    except Exception:
                        pass

                    duration_ms = self._record_item_result(
                        item_id=item_id,
                        status="failed",
                        item_start=item_start,
                        item_results=item_results,
                        current=idx + 1,
                        total=total,
                        error=str(e),
                        item_data=(
                            {"errorScreen": error_screen} if error_screen else None
                        ),
                    )
                    log.warning(
                        "Item failed",
                        item=item_id,
                        error=str(e),
                        duration_ms=duration_ms,
                    )

                    try:
                        log.info("Attempting recovery logoff...")
                        self.logoff(host)
                    except Exception:
                        log.warning("Recovery logoff failed, continuing...")

            success_count = sum(1 for r in item_results if r.status == "success")
            failed_count = sum(1 for r in item_results if r.status == "failed")
            skipped_count = sum(1 for r in item_results if r.status == "skipped")

            if not self.is_cancelled:
                result.status = ASTStatus.SUCCESS
                result.message = (
                    f"Processed {total} items "
                    f"({success_count} success, {failed_count} failed, {skipped_count} skipped)"
                )
            result.item_results = item_results
            result.data.update(
                {
                    "successCount": success_count,
                    "failedCount": failed_count,
                    "skippedCount": skipped_count,
                }
            )

            result.screenshots = all_screenshots

            if self.is_cancelled:
                self._update_execution_record(
                    "cancelled", result.message or "Cancelled by user", item_results
                )
                log.info("AST cancelled", username=username)
            else:
                self._update_execution_record(
                    "success", result.message or "", item_results
                )
                log.info("AST completed successfully", username=username)

        except Exception as e:
            result.status = ASTStatus.FAILED
            result.error = str(e)
            result.message = f"Error during execution: {e}"
            try:
                all_screenshots.append(host.show_screen("Error State"))
            except Exception:
                pass
            result.screenshots = all_screenshots
            result.item_results = item_results

            self._update_execution_record(
                "failed", result.message, item_results, error=str(e)
            )
            log.exception("AST failed", username=username)

        return result

    # ------------------------------------------------------------------ #
    # Parallel Execution using ATI
    # ------------------------------------------------------------------ #
    def execute_parallel(
        self,
        host_config: dict[str, Any],
        max_workers: int = 10,
        **kwargs: Any,
    ) -> ASTResult:
        """
        Execute items in parallel using ATI sessions.

        Creates a new ATI session for each item and processes items in parallel
        batches. Each session gets its own Host instance.

        Args:
            host_config: Configuration for connecting to the host, including:
                - host: Hostname or IP address
                - port: Port number
                - secure: Whether to use TLS (default: False)
                - verifycert: Whether to verify TLS cert (default: False)
            max_workers: Maximum number of parallel workers (default: 10)
            **kwargs: Additional parameters for the AST, including:
                - username: TSO username (required)
                - password: TSO password (required)
                - policyNumbers or items: List of items to process

        Returns:
            ASTResult with execution status and data
        """
        from tnz.ati import Ati

        from ..services.tn3270.host import Host

        username = kwargs.get("username")
        password = kwargs.get("password")
        raw_items: list[Any] = self.prepare_items(**kwargs)
        app_user_id: str = kwargs.get("userId", "anonymous")
        self._execution_id = kwargs.get("execution_id") or str(uuid4())
        self._session_id = kwargs.get("sessionId", self._execution_id)

        if not username or not password:
            return ASTResult(
                status=ASTStatus.FAILED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                message="Missing required parameters: username and password are required",
                error="ValidationError: username and password must be provided",
            )

        result = ASTResult(
            status=ASTStatus.RUNNING,
            started_at=datetime.now(),
            data={"username": username, "policyCount": len(raw_items)},
        )

        all_screenshots: list[str] = []
        item_results: list[ItemResult] = []
        processed_count = 0
        total = len(raw_items)

        # Thread-safe lock for updating shared state
        results_lock = threading.Lock()

        self._init_db()
        self._create_execution_record(
            username,
            app_user_id,
            total,
            result.started_at or datetime.now(),
        )

        def process_item_with_ati(
            item: Any, index: int
        ) -> tuple[str, Literal["success", "failed", "skipped"], int, str | None, dict[str, Any] | None]:
            """Process a single item using a dedicated ATI session."""
            item_id = self.get_item_id(item)
            item_start = datetime.now()

            if not self.validate_item(item):
                item_end = datetime.now()
                duration_ms = int((item_end - item_start).total_seconds() * 1000)
                return item_id, "skipped", duration_ms, "Invalid item", None

            # Create a unique session name for this item
            session_name = f"SESSION_{self._execution_id}_{index}"

            ati_instance: Ati | None = None
            try:
                # Create new ATI instance for this item
                ati_instance = Ati()

                # Configure session variables
                host_addr = host_config.get("host", "localhost")
                port = host_config.get("port", 3270)
                secure = host_config.get("secure", False)
                verifycert = host_config.get("verifycert", False)

                # Set ATI variables for connection
                ati_instance.set("SESSION_HOST", host_addr, xtern=False)
                ati_instance.set("SESSION_PORT", str(port), xtern=False)
                if secure:
                    ati_instance.set("SESSION_SSL", "1", xtern=False)

                # Create the session
                rc = ati_instance.set("SESSION", session_name, verifycert=verifycert)
                if rc not in (0, 1):
                    raise Exception(f"Failed to establish ATI session: RC={rc}")

                # Get the tnz instance from ATI
                tnz = ati_instance.get_tnz(session_name)
                if not tnz:
                    raise Exception("Failed to get tnz instance from ATI session")

                # Wait for initial screen
                ati_instance.wait(2)

                # Create Host wrapper
                host = Host(tnz)

                # Authenticate
                success, error, screenshots = self.authenticate(
                    host,
                    user=username,
                    password=password,
                    expected_keywords_after_login=self.auth_expected_keywords,
                    application=self.auth_application,
                    group=self.auth_group,
                )
                with results_lock:
                    all_screenshots.extend(screenshots)

                if not success:
                    raise Exception(f"Login failed: {error}")

                # Process the item
                success, error, item_data = self.process_single_item(
                    host, item, index + 1, total
                )
                if not success:
                    raise Exception(f"Process failed: {error}")

                # Logoff
                success, error, screenshots = self.logoff(host)
                with results_lock:
                    all_screenshots.extend(screenshots)
                if not success:
                    log.warning("Logoff failed", item=item_id, error=error)

                item_end = datetime.now()
                duration_ms = int((item_end - item_start).total_seconds() * 1000)

                log.info(
                    "Item completed successfully (parallel)",
                    item=item_id,
                    duration_ms=duration_ms,
                )

                return item_id, "success", duration_ms, None, item_data

            except Exception as e:
                item_end = datetime.now()
                duration_ms = int((item_end - item_start).total_seconds() * 1000)
                log.warning(
                    "Item failed (parallel)",
                    item=item_id,
                    error=str(e),
                    duration_ms=duration_ms,
                )
                return item_id, "failed", duration_ms, str(e), None

            finally:
                # Clean up ATI session
                if ati_instance is not None:
                    try:
                        ati_instance.drop(session_name)
                    except Exception:
                        pass

        try:
            if not raw_items:
                log.info("No items to process, returning early")
                result.status = ASTStatus.SUCCESS
                result.message = "No items to process"
                return result

            log.info(f"Processing {total} items in parallel (max {max_workers} workers)...")

            # Process items in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="ast_parallel"
            ) as executor:
                # Submit all items for processing
                future_to_item = {
                    executor.submit(process_item_with_ati, item, idx): (item, idx)
                    for idx, item in enumerate(raw_items)
                }

                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_item):
                    if self._cancelled:
                        # Cancel remaining futures
                        for f in future_to_item:
                            f.cancel()
                        break

                    item, idx = future_to_item[future]
                    item_id = self.get_item_id(item)

                    try:
                        (
                            result_item_id,
                            status,
                            duration_ms,
                            error,
                            item_data,
                        ) = future.result()

                        # Record result
                        item_start = datetime.now() - timedelta(
                            milliseconds=duration_ms
                        )
                        item_result = ItemResult(
                            item_id=result_item_id,
                            status=status,
                            started_at=item_start,
                            completed_at=datetime.now(),
                            duration_ms=duration_ms,
                            error=error,
                            data=item_data or {},
                        )

                        with results_lock:
                            item_results.append(item_result)
                            processed_count += 1

                        # Report progress and result
                        self.report_item_result(
                            item_id=result_item_id,
                            status=status,
                            duration_ms=duration_ms,
                            error=error,
                            data=item_data,
                        )

                        self._save_item_result(
                            item_id=result_item_id,
                            status=status,
                            duration_ms=duration_ms,
                            started_at=item_start,
                            completed_at=datetime.now(),
                            error=error,
                            item_data=item_data,
                        )

                        self.report_progress(
                            current=processed_count,
                            total=total,
                            current_item=result_item_id,
                            item_status=status,
                            message=f"Item {processed_count}/{total}: {status}",
                        )

                    except Exception as e:
                        log.exception("Error processing future result", item=item_id)
                        with results_lock:
                            processed_count += 1
                            item_results.append(
                                ItemResult(
                                    item_id=item_id,
                                    status="failed",
                                    started_at=datetime.now(),
                                    completed_at=datetime.now(),
                                    duration_ms=0,
                                    error=str(e),
                                )
                            )

            success_count = sum(1 for r in item_results if r.status == "success")
            failed_count = sum(1 for r in item_results if r.status == "failed")
            skipped_count = sum(1 for r in item_results if r.status == "skipped")

            if self._cancelled:
                result.status = ASTStatus.CANCELLED
                result.message = f"Cancelled by user. Processed {processed_count}/{total} items."
            else:
                result.status = ASTStatus.SUCCESS
                result.message = (
                    f"Processed {total} items in parallel "
                    f"({success_count} success, {failed_count} failed, {skipped_count} skipped)"
                )

            result.item_results = item_results
            result.data.update(
                {
                    "successCount": success_count,
                    "failedCount": failed_count,
                    "skippedCount": skipped_count,
                    "parallelWorkers": max_workers,
                }
            )
            result.screenshots = all_screenshots

            if self._cancelled:
                self._update_execution_record(
                    "cancelled", result.message, item_results
                )
                log.info("AST cancelled (parallel)", username=username)
            else:
                self._update_execution_record("success", result.message, item_results)
                log.info("AST completed successfully (parallel)", username=username)

        except Exception as e:
            result.status = ASTStatus.FAILED
            result.error = str(e)
            result.message = f"Error during parallel execution: {e}"
            result.screenshots = all_screenshots
            result.item_results = item_results

            self._update_execution_record(
                "failed", result.message, item_results, error=str(e)
            )
            log.exception("AST failed (parallel)", username=username)

        result.completed_at = datetime.now()
        return result
