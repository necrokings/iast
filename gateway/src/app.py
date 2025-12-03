# ============================================================================
# PTY Gateway Application
# ============================================================================

import asyncio
import signal

import structlog

from .core import get_config
from .services import (
    close_valkey_client,
    get_pty_manager,
    get_tn3270_manager,
    init_pty_manager,
    init_tn3270_manager,
    init_valkey_client,
)

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()

_shutdown_event: asyncio.Event | None = None


async def shutdown(sig: signal.Signals | None = None) -> None:
    """Graceful shutdown handler."""
    if sig:
        log.info("Received shutdown signal", signal=sig.name)
    else:
        log.info("Shutting down")

    # Destroy all PTY sessions
    try:
        pty_manager = get_pty_manager()
        await pty_manager.destroy_all_sessions()
    except RuntimeError:
        pass

    # Destroy all TN3270 sessions
    try:
        tn3270_manager = get_tn3270_manager()
        await tn3270_manager.destroy_all_sessions()
    except RuntimeError:
        pass

    # Close Valkey connection
    await close_valkey_client()

    log.info("Shutdown complete")

    # Signal main loop to exit
    if _shutdown_event:
        _shutdown_event.set()


async def async_main() -> None:
    """Async main entry point."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    config = get_config()

    log.info(
        "Starting PTY Gateway",
        valkey_host=config.valkey.host,
        valkey_port=config.valkey.port,
        pty_max_sessions=config.pty.max_sessions,
        tn3270_host=config.tn3270.host,
        tn3270_port=config.tn3270.port,
        tn3270_max_sessions=config.tn3270.max_sessions,
    )

    # Initialize Valkey client
    valkey = await init_valkey_client(config.valkey)

    # Initialize PTY manager and start listening
    pty_manager = init_pty_manager(config.pty, valkey)
    await pty_manager.start()

    # Initialize TN3270 manager and start listening
    tn3270_manager = init_tn3270_manager(config.tn3270, valkey)
    await tn3270_manager.start()

    # Setup signal handlers
    loop = asyncio.get_running_loop()

    def handle_signal(sig: signal.Signals) -> None:
        asyncio.create_task(shutdown(sig))

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    log.info("PTY Gateway ready, waiting for connections...")

    # Keep running until shutdown
    await _shutdown_event.wait()


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        # Run cleanup synchronously
        asyncio.run(shutdown())


if __name__ == "__main__":
    main()
