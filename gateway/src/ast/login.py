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
from typing import TYPE_CHECKING, Any, Literal

import structlog

from .base import AST

if TYPE_CHECKING:
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

    # Authentication configuration for Fire system
    auth_expected_keywords = ["Fire System Selection"]
    auth_application = "FIRE06"
    auth_group = "@OOFIRE"

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

    def sign_off(
        self, host: "Host", target_screen_keywords: list[str] | None = None
    ) -> bool:
        """
        Sign off from TSO system.

        Args:
            host: Host automation interface
            target_screen_keywords: Optional list of keywords to verify sign-off reached target screen

        Returns:
            True if sign-off successful, False otherwise
        """
        log.info("🔒 Signing off from terminal session...")
        max_backoff_count = 20
        while (
            not host.wait_for_text("Exit Menu", timeout=0.8) and max_backoff_count > 0
        ):
            host.pf(15)
            max_backoff_count -= 1

        host.show_screen("Exit Menu")
        host.fill_field_at_position(36, 5, "1")
        host.show_screen("Confirm Exit")
        host.enter()

        # Check for target screen or default SIGNON
        target_keywords = target_screen_keywords or ["**** SIGNON ****", "SIGNON"]
        for keyword in target_keywords:
            if host.wait_for_text(keyword, timeout=10):
                log.info("✅ Signed off successfully.", keyword=keyword)
                return True

        log.warning("Failed to reach expected sign-off screen")
        return False

    def logoff(self, host: "Host", target_screen_keywords: list[str] | None = None) -> tuple[bool, str]:
        """Implement abstract logoff using sign_off."""
        log.info("🔒 Signing off from terminal session...")
        max_backoff_count = 20
        while (
            not host.wait_for_text("Exit Menu", timeout=0.8) and max_backoff_count > 0
        ):
            host.pf(15)
            max_backoff_count -= 1

        host.show_screen("Exit Menu")
        host.fill_field_at_position(36, 5, "1")
        host.show_screen("Confirm Exit")
        host.enter()

        # Check for target screen or default SIGNON
        target_keywords = target_screen_keywords or ["**** SIGNON ****", "SIGNON"]
        for keyword in target_keywords:
            if host.wait_for_text(keyword, timeout=10):
                log.info("✅ Signed off successfully.", keyword=keyword)
                host.show_screen("Signed Off")
                return True, ""

        host.show_screen("Sign Off Failed")
        return False, "Failed to sign off"

    def validate_item(self, item: Any) -> bool:
        return validate_policy_number(str(item))

    def process_single_item(
        self, host: "Host", item: Any, index: int, total: int
    ) -> tuple[bool, str, dict[str, Any]]:
        return self._phase2_process_policy(host, str(item))
