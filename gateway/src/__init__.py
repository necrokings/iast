# ============================================================================
# Terminal Gateway Package
# ============================================================================
"""
TN3270 Gateway for terminal sessions.

Structure:
    src/
    ├── core/           # Configuration, errors, channels
    ├── models/         # Pydantic message models
    ├── services/       # Valkey client, TN3270 manager
    └── app.py          # Application entry point
"""

from .app import main
from .core import (
    TN3270_CONTROL_CHANNEL,
    Config,
    ErrorCodes,
    TN3270Config,
    TerminalError,
    ValkeyConfig,
    get_config,
    get_tn3270_input_channel,
    get_tn3270_output_channel,
)
from .models import (
    DataMessage,
    ErrorMessage,
    MessageEnvelope,
    MessageType,
    PingMessage,
    PongMessage,
    SessionCreatedMessage,
    SessionCreateMessage,
    SessionDestroyedMessage,
    SessionDestroyMessage,
    create_data_message,
    create_error_message,
    create_session_created_message,
    create_session_destroyed_message,
    parse_message,
    serialize_message,
)
from .services import (
    TN3270Manager,
    TN3270Session,
    TN3270Renderer,
    ValkeyClient,
    close_valkey_client,
    get_tn3270_manager,
    get_valkey_client,
    init_tn3270_manager,
    init_valkey_client,
)

__all__ = [
    # App
    "main",
    # Channels
    "get_tn3270_input_channel",
    "get_tn3270_output_channel",
    "TN3270_CONTROL_CHANNEL",
    # Config
    "Config",
    "ValkeyConfig",
    "TN3270Config",
    "get_config",
    # Errors
    "ErrorCodes",
    "TerminalError",
    # Models
    "MessageType",
    "DataMessage",
    "PingMessage",
    "PongMessage",
    "ErrorMessage",
    "SessionCreateMessage",
    "SessionDestroyMessage",
    "SessionCreatedMessage",
    "SessionDestroyedMessage",
    "MessageEnvelope",
    "parse_message",
    "serialize_message",
    "create_data_message",
    "create_error_message",
    "create_session_created_message",
    "create_session_destroyed_message",
    # TN3270 Manager
    "TN3270Manager",
    "TN3270Session",
    "TN3270Renderer",
    "get_tn3270_manager",
    "init_tn3270_manager",
    # Valkey Client
    "ValkeyClient",
    "get_valkey_client",
    "init_valkey_client",
    "close_valkey_client",
]
