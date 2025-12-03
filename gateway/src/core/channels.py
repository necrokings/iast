# ============================================================================
# Valkey Channel Helpers (matching @terminal/shared)
# ============================================================================

"""
Channel naming conventions:
- gateway.control        - Global control channel for PTY session creation
- tn3270.control         - Global control channel for TN3270 session creation
- pty.input.<id>         - Input to PTY (keystrokes from user)
- pty.output.<id>        - Output from PTY (terminal output)
- pty.control.<id>       - Control messages (resize, destroy)
- tn3270.input.<id>      - Input to TN3270 (keystrokes from user)
- tn3270.output.<id>     - Output from TN3270 (terminal output)
"""


def get_pty_input_channel(session_id: str) -> str:
    """Get the input channel for a PTY session."""
    return f"pty.input.{session_id}"


def get_pty_output_channel(session_id: str) -> str:
    """Get the output channel for a PTY session."""
    return f"pty.output.{session_id}"


def get_pty_control_channel(session_id: str) -> str:
    """Get the control channel for a PTY session."""
    return f"pty.control.{session_id}"


def get_tn3270_input_channel(session_id: str) -> str:
    """Get the input channel for a TN3270 session."""
    return f"tn3270.input.{session_id}"


def get_tn3270_output_channel(session_id: str) -> str:
    """Get the output channel for a TN3270 session."""
    return f"tn3270.output.{session_id}"


# Control channel for all PTY gateway instances
GATEWAY_CONTROL_CHANNEL = "gateway.control"

# Control channel for TN3270 gateway instances
TN3270_CONTROL_CHANNEL = "tn3270.control"
