# ============================================================================
# Configuration
# ============================================================================

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ValkeyConfig:
    """Valkey/Redis connection configuration."""

    host: str = field(default_factory=lambda: os.getenv("VALKEY_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("VALKEY_PORT", "6379")))
    db: int = field(default_factory=lambda: int(os.getenv("VALKEY_DB", "0")))
    password: str | None = field(default_factory=lambda: os.getenv("VALKEY_PASSWORD"))


@dataclass(frozen=True)
class PTYConfig:
    """PTY session configuration."""

    shell: str = field(default_factory=lambda: os.getenv("PTY_SHELL", "/bin/zsh"))
    cols: int = field(default_factory=lambda: int(os.getenv("PTY_COLS", "80")))
    rows: int = field(default_factory=lambda: int(os.getenv("PTY_ROWS", "24")))
    max_sessions: int = field(
        default_factory=lambda: int(os.getenv("PTY_MAX_SESSIONS", "10"))
    )
    idle_timeout: int = field(
        default_factory=lambda: int(os.getenv("PTY_IDLE_TIMEOUT", "3600"))
    )


@dataclass(frozen=True)
class TN3270Config:
    """TN3270 terminal session configuration.

    Uses IBM-3278-4-E model (80x43) by default.
    """

    host: str = field(default_factory=lambda: os.getenv("TN3270_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("TN3270_PORT", "3270")))
    # IBM-3278-4-E: 80 columns x 43 rows (fixed, does not resize)
    cols: int = field(default_factory=lambda: int(os.getenv("TN3270_COLS", "80")))
    rows: int = field(default_factory=lambda: int(os.getenv("TN3270_ROWS", "43")))
    terminal_type: str = field(
        default_factory=lambda: os.getenv("TN3270_TERMINAL_TYPE", "IBM-3278-4-E")
    )
    max_sessions: int = field(
        default_factory=lambda: int(os.getenv("TN3270_MAX_SESSIONS", "10"))
    )
    secure: bool = field(
        default_factory=lambda: os.getenv("TN3270_SECURE", "false").lower() == "true"
    )


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    valkey: ValkeyConfig = field(default_factory=ValkeyConfig)
    pty: PTYConfig = field(default_factory=PTYConfig)
    tn3270: TN3270Config = field(default_factory=TN3270Config)


_config: Config | None = None


def get_config() -> Config:
    """Get application configuration (singleton)."""
    global _config
    if _config is None:
        _config = Config()
    return _config
