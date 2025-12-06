# ============================================================================
# Login AST - Automated Login to TSO
# ============================================================================
"""
Automated login script for TK4- MVS system.

This AST performs a complete login/logoff cycle for each policy:
1. Phase 1: Login (Wait for Logon screen, enter credentials, navigate to TSO)
2. Phase 2: Process policy number
3. Phase 3: Logoff (Exit TSO and logoff)

Each policy gets its own full login/logoff cycle.
"""

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Optional

import structlog

from ..db import get_dynamodb_client
from .base import AST, ASTResult, ASTStatus, ItemResult

if TYPE_CHECKING:
    from ..db import DynamoDBClient
    from ..services.tn3270.host import Host

log = structlog.get_logger()

PolicyStatus = Literal["success", "failed", "skipped"]


def validate_policy_number(policy_number: str) -> bool:
    """Validate a policy number format (9 char alphanumeric)."""
    return bool(policy_number and len(policy_number) == 9 and policy_number.isalnum())


class LoginAST(AST):
    """
    Automated login to TK4- TSO system.

    Performs a complete login/logoff cycle for each policy number.
    Each policy goes through all three phases:
    - Phase 1: Login
    - Phase 2: Process policy
    - Phase 3: Logoff

    Required parameters:
        - username: TSO username
        - password: TSO password

    Optional parameters:
        - policyNumbers: List of 9-char policy numbers to process
    """

    name = "login"
    description = "Login to TSO and process policies (full cycle per policy)"

    def __init__(self) -> None:
        super().__init__()
        self._db: Optional["DynamoDBClient"] = None
        self._session_id: str = ""

    # ========================================================================
    # Helper Methods for DynamoDB Operations
    # ========================================================================

    def _init_db(self) -> None:
        """Initialize DynamoDB client, required for persistence."""
        self._db = get_dynamodb_client()

    def _save_policy_result(
        self,
        policy_number: str,
        status: PolicyStatus,
        duration_ms: int,
        started_at: datetime,
        completed_at: datetime,
        error: Optional[str] = None,
        policy_data: Optional[dict] = None,
    ) -> None:
        """Save a policy result to DynamoDB."""
        try:
            data: dict[str, Any] = {
                "status": status,
                "duration_ms": duration_ms,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "entity_type": "POLICY_RESULT",
            }
            if error:
                data["error"] = error
            if policy_data:
                data["policy_data"] = policy_data

            self._db.put_policy_result(
                execution_id=self._execution_id,
                policy_number=policy_number,
                data=data,
            )
        except Exception as e:
            log.warning("Failed to save policy result", policy=policy_number, error=str(e))

    def _create_execution_record(
        self,
        username: str,
        user_id: str,
        policy_count: int,
        started_at: datetime,
    ) -> None:
        """Create an execution record in DynamoDB."""
        try:
            self._db.put_execution(
                session_id=self._session_id,
                execution_id=self._execution_id,
                data={
                    "ast_name": self.name,
                    "user_id": user_id,
                    "host_user": username,
                    "policy_count": policy_count,
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
        except Exception as e:
            log.warning("Failed to create execution record", error=str(e))

    def _update_execution_record(
        self,
        status: str,
        message: str,
        item_results: list[ItemResult],
        error: Optional[str] = None,
    ) -> None:
        """Update execution record with final status."""
        try:
            updates: dict[str, Any] = {
                "status": status,
                "completed_at": datetime.now().isoformat(),
                "message": message,
            }

            if error:
                updates["error"] = error
            else:
                updates["success_count"] = sum(1 for r in item_results if r.status == "success")
                updates["failed_count"] = sum(1 for r in item_results if r.status == "failed")
                updates["skipped_count"] = sum(1 for r in item_results if r.status == "skipped")

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
        except Exception as e:
            log.warning("Failed to update execution record", error=str(e))

    # ========================================================================
    # Helper Methods for Policy Processing
    # ========================================================================

    def _record_policy_result(
        self,
        policy_number: str,
        status: PolicyStatus,
        item_start: datetime,
        item_results: list[ItemResult],
        current: int,
        total: int,
        error: Optional[str] = None,
        policy_data: Optional[dict] = None,
    ) -> int:
        """
        Record a policy result: create ItemResult, report to WebSocket, save to DB, report progress.

        Returns:
            Duration in milliseconds.
        """
        item_end = datetime.now()
        duration_ms = int((item_end - item_start).total_seconds() * 1000)

        # Create and store ItemResult
        item_result = ItemResult(
            item_id=policy_number,
            status=status,
            started_at=item_start,
            completed_at=item_end,
            duration_ms=duration_ms,
            error=error,
            data=policy_data or {},
        )
        item_results.append(item_result)

        # Report via WebSocket
        self.report_item_result(
            item_id=policy_number,
            status=status,
            duration_ms=duration_ms,
            error=error,
            data=policy_data,
        )

        # Save to DynamoDB
        self._save_policy_result(
            policy_number=policy_number,
            status=status,
            duration_ms=duration_ms,
            started_at=item_start,
            completed_at=item_end,
            error=error,
            policy_data=policy_data,
        )

        # Report progress
        message = f"Policy {current}/{total}: "
        if status == "success":
            message += "Completed"
        elif status == "failed":
            message += f"Failed - {error}"
        else:
            message += "Skipped"

        self.report_progress(
            current=current,
            total=total,
            current_item=policy_number,
            item_status=status,
            message=message,
        )

        return duration_ms

    # ========================================================================
    # Phase Methods
    # ========================================================================

    def _phase1_login(
        self, host: "Host", username: str, password: str
    ) -> tuple[bool, str, list[str]]:
        """
        Phase 1: Login to TSO.

        Returns:
            Tuple of (success, error_message, screenshots)
        """
        screenshots: list[str] = []

        # Step 1: Wait for Logon screen (up to 2 minutes)
        log.info("Phase 1.1: Waiting for Logon screen...")
        if not host.wait_for_text("Logon", timeout=120):
            return False, "Timeout waiting for Logon screen", screenshots

        screenshots.append(host.show_screen("Logon Screen"))

        # Step 2: Enter username
        log.info(f"Phase 1.2: Entering username '{username}'...")
        host.fill_field_by_label("Logon", username)
        host.enter()

        # Step 3: Wait for password prompt and enter password
        log.info("Phase 1.3: Waiting for password prompt...")
        if not host.wait_for_text("ENTER CURRENT PASSWORD FOR", timeout=30):
            return False, "Failed to reach password prompt", screenshots

        screenshots.append(host.show_screen("Password Prompt"))

        # Enter password
        log.info("Phase 1.4: Entering password...")
        host.fill_field_at_position(1, 1, password)
        host.enter()

        # Step 4: Wait for Welcome message
        log.info("Phase 1.5: Waiting for Welcome message...")
        if not host.wait_for_text("Welcome to the TSO system", timeout=60):
            return False, "Failed to reach Welcome screen", screenshots

        screenshots.append(host.show_screen("Welcome Screen"))
        host.enter()

        # Step 5: Wait for fortune cookie
        log.info("Phase 1.6: Waiting for fortune cookie...")
        if not host.wait_for_text("fortune cookie", timeout=30):
            return False, "Failed to reach fortune cookie screen", screenshots

        screenshots.append(host.show_screen("Fortune Cookie"))
        host.enter()

        # Step 6: Wait for TSO Applications menu
        log.info("Phase 1.7: Waiting for TSO Applications menu...")
        if not host.wait_for_text("TSO Applications", timeout=30):
            return False, "Failed to reach TSO Applications menu", screenshots

        screenshots.append(host.show_screen("TSO Applications"))

        return True, "", screenshots

    def _phase2_process_policy(
        self, host: "Host", policy_number: str
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Phase 2: Process a single policy number.

        Returns:
            Tuple of (success, error_message, policy_data)
        """
        log.info(f"Phase 2: Processing policy {policy_number}...")

        # TODO: In a real implementation, this would:
        # 1. Navigate to policy lookup screen
        # 2. Enter the policy number
        # 3. Read the policy data
        # 4. Extract relevant information

        # For now, simulate processing with a small delay
        time.sleep(0.5)  # Simulate processing time

        policy_data = {
            "policyNumber": policy_number,
            "status": "active",
        }

        return True, "", policy_data

    def _phase3_logoff(self, host: "Host") -> tuple[bool, str, list[str]]:
        """
        Phase 3: Logoff from TSO.

        Returns:
            Tuple of (success, error_message, screenshots)
        """
        screenshots: list[str] = []

        # Step 1: Exit with PF3
        log.info("Phase 3.1: Pressing PF3 to exit...")
        host.pf(3)

        # Step 2: Wait for termination message
        log.info("Phase 3.2: Waiting for termination message...")
        if not host.wait_for_text("TSO Applications Menu terminated", timeout=30):
            return False, "Failed to exit TSO Applications", screenshots

        screenshots.append(host.show_screen("Menu Terminated"))

        # Step 3: Logoff
        log.info("Phase 3.3: Logging off...")
        host.type_text("logoff")
        host.enter()

        screenshots.append(host.show_screen("After Logoff"))

        # Wait a moment for logoff to complete
        time.sleep(0.5)

        return True, "", screenshots

    def _process_single_policy(
        self,
        host: "Host",
        policy_number: str,
        username: str,
        password: str,
        current: int,
        total: int,
        all_screenshots: list[str],
        item_results: list[ItemResult],
    ) -> None:
        """Process a single policy through all three phases."""
        item_start = datetime.now()

        # Report progress: starting this policy
        self.report_progress(
            current=current,
            total=total,
            current_item=policy_number,
            item_status="running",
            message=f"Policy {current}/{total}: Phase 1 - Logging in",
        )

        # Validate policy number format first
        if not validate_policy_number(policy_number):
            self._record_policy_result(
                policy_number=policy_number,
                status="skipped",
                item_start=item_start,
                item_results=item_results,
                current=current,
                total=total,
                error="Invalid policy number format",
            )
            return

        try:
            # Phase 1: Login
            success, error, screenshots = self._phase1_login(host, username, password)
            all_screenshots.extend(screenshots)
            if not success:
                raise Exception(f"Phase 1 failed: {error}")

            # Phase 2: Process Policy
            self.report_progress(
                current=current,
                total=total,
                current_item=policy_number,
                item_status="running",
                message=f"Policy {current}/{total}: Phase 2 - Processing",
            )
            success, error, policy_data = self._phase2_process_policy(host, policy_number)
            if not success:
                raise Exception(f"Phase 2 failed: {error}")

            # Phase 3: Logoff
            self.report_progress(
                current=current,
                total=total,
                current_item=policy_number,
                item_status="running",
                message=f"Policy {current}/{total}: Phase 3 - Logging off",
            )
            success, error, screenshots = self._phase3_logoff(host)
            all_screenshots.extend(screenshots)
            if not success:
                raise Exception(f"Phase 3 failed: {error}")

            # Success
            duration_ms = self._record_policy_result(
                policy_number=policy_number,
                status="success",
                item_start=item_start,
                item_results=item_results,
                current=current,
                total=total,
                policy_data=policy_data,
            )
            log.info(
                f"Policy {policy_number} completed successfully",
                duration_ms=duration_ms,
            )

        except Exception as e:
            # Capture the current screen when a failure occurs
            error_screen = None
            try:
                error_screen = host.get_formatted_screen(show_row_numbers=False)
            except Exception:
                pass  # Ignore screen capture errors

            duration_ms = self._record_policy_result(
                policy_number=policy_number,
                status="failed",
                item_start=item_start,
                item_results=item_results,
                current=current,
                total=total,
                error=str(e),
                policy_data={"errorScreen": error_screen} if error_screen else None,
            )
            log.warning(f"Policy {policy_number} failed", error=str(e), duration_ms=duration_ms)

            # Try to recover by logging off
            try:
                log.info("Attempting recovery logoff...")
                self._phase3_logoff(host)
            except Exception:
                log.warning("Recovery logoff failed, continuing...")

    def execute(self, host: "Host", **kwargs: Any) -> ASTResult:
        """
        Execute the login automation.

        For each policy number:
        1. Phase 1: Login to TSO
        2. Phase 2: Process the policy
        3. Phase 3: Logoff from TSO
        """
        username = kwargs.get("username")
        password = kwargs.get("password")
        policy_numbers: list[str] = kwargs.get("policyNumbers", []) or []
        app_user_id: str = kwargs.get("userId", "anonymous")
        self._session_id = kwargs.get("sessionId", self._execution_id)

        # Validate required parameters
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
            data={"username": username, "policyCount": len(policy_numbers)},
        )

        all_screenshots: list[str] = []
        item_results: list[ItemResult] = []

        # Initialize DynamoDB and create execution record
        self._init_db()
        self._create_execution_record(
            username,
            app_user_id,
            len(policy_numbers),
            result.started_at or datetime.now(),
        )

        try:
            if not policy_numbers:
                # No policies - just do a single login/logoff cycle
                log.info("No policies to process, doing single login/logoff cycle")

                success, error, screenshots = self._phase1_login(host, username, password)
                all_screenshots.extend(screenshots)
                if not success:
                    raise Exception(error)

                success, error, screenshots = self._phase3_logoff(host)
                all_screenshots.extend(screenshots)
                if not success:
                    raise Exception(error)

                result.status = ASTStatus.SUCCESS
                result.message = f"Successfully logged in and out as {username}"
            else:
                # Process each policy with full login/logoff cycle
                total = len(policy_numbers)
                log.info(f"Processing {total} policies (full cycle each)...")

                for idx, policy_number in enumerate(policy_numbers):
                    # Check for pause/cancel before processing next policy
                    if not self.wait_if_paused():
                        log.info("AST cancelled by user")
                        result.status = ASTStatus.CANCELLED
                        result.message = "Cancelled by user"
                        break

                    self._process_single_policy(
                        host=host,
                        policy_number=policy_number,
                        username=username,
                        password=password,
                        current=idx + 1,
                        total=total,
                        all_screenshots=all_screenshots,
                        item_results=item_results,
                    )

                # Calculate summary
                success_count = sum(1 for r in item_results if r.status == "success")
                failed_count = sum(1 for r in item_results if r.status == "failed")
                skipped_count = sum(1 for r in item_results if r.status == "skipped")

                if not self.is_cancelled:
                    result.status = ASTStatus.SUCCESS
                    result.message = (
                        f"Processed {total} policies "
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

            # Update execution record based on final status
            if self.is_cancelled:
                self._update_execution_record(
                    "cancelled", result.message or "Cancelled by user", item_results
                )
                log.info("Login AST cancelled", username=username)
            else:
                self._update_execution_record("success", result.message or "", item_results)
                log.info("Login AST completed successfully", username=username)

        except Exception as e:
            result.status = ASTStatus.FAILED
            result.error = str(e)
            result.message = f"Error during login: {e}"
            all_screenshots.append(host.show_screen("Error State"))
            result.screenshots = all_screenshots
            result.item_results = item_results

            self._update_execution_record("failed", result.message, item_results, error=str(e))
            log.exception("Login AST failed", username=username)

        return result
