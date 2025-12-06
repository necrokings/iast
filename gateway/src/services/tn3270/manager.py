# ============================================================================
# TN3270 Session Manager
# ============================================================================
"""
Manages TN3270 terminal sessions using the tnz library.

Each session connects to a 3270 host (like Hercules mainframe emulator)
and provides:
- Screen rendering to ANSI for xterm.js
- Key input handling (3270 keys like PF1-24, PA1-3, Enter, Clear)
- Session lifecycle management

Note: tnz uses its own event loop internally, so we run it in a separate
thread to avoid conflicts with the main asyncio event loop.
"""

import asyncio
import concurrent.futures
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import structlog

from ...ast import LoginAST
from ...ast.base import AST
from ...core import ErrorCodes, TerminalError, TN3270Config
from ...models import (
    ASTControlMessage,
    ASTRunMessage,
    DataMessage,
    ResizeMessage,
    SessionCreateMessage,
    SessionDestroyMessage,
    TN3270Field,
    create_ast_item_result_message,
    create_ast_paused_message,
    create_ast_progress_message,
    create_ast_status_message,
    create_data_message,
    create_error_message,
    create_session_created_message,
    create_session_destroyed_message,
    create_tn3270_screen_message,
    parse_message,
    serialize_message,
)
from .host import Host
from .renderer import TN3270Renderer

if TYPE_CHECKING:
    from ..valkey import ValkeyClient

from tnz import tnz as tnz_module

log = structlog.get_logger()

# Thread pool for running blocking tnz operations
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="tnz")


# 3270 key mappings from xterm.js input
KEY_MAPPINGS = {
    # Function keys
    "\x1bOP": "pf1",  # F1
    "\x1bOQ": "pf2",  # F2
    "\x1bOR": "pf3",  # F3
    "\x1bOS": "pf4",  # F4
    "\x1b[15~": "pf5",  # F5
    "\x1b[17~": "pf6",  # F6
    "\x1b[18~": "pf7",  # F7
    "\x1b[19~": "pf8",  # F8
    "\x1b[20~": "pf9",  # F9
    "\x1b[21~": "pf10",  # F10
    "\x1b[23~": "pf11",  # F11
    "\x1b[24~": "pf12",  # F12
    # Shift+F1-F12 for PF13-PF24
    "\x1b[1;2P": "pf13",
    "\x1b[1;2Q": "pf14",
    "\x1b[1;2R": "pf15",
    "\x1b[1;2S": "pf16",
    "\x1b[15;2~": "pf17",
    "\x1b[17;2~": "pf18",
    "\x1b[18;2~": "pf19",
    "\x1b[19;2~": "pf20",
    "\x1b[20;2~": "pf21",
    "\x1b[21;2~": "pf22",
    "\x1b[23;2~": "pf23",
    "\x1b[24;2~": "pf24",
    # Navigation
    "\x1b[A": "key_curup",  # Up
    "\x1b[B": "key_curdown",  # Down
    "\x1b[C": "key_curright",  # Right
    "\x1b[D": "key_curleft",  # Left
    "\x1b[H": "key_home",  # Home
    "\x1b[F": "key_end",  # End
    "\x1b[1~": "key_home",  # Home (alternate)
    "\x1b[4~": "key_end",  # End (alternate)
    # Special keys
    "\r": "enter",  # Enter
    "\n": "enter",  # Enter (alternate)
    "\t": "key_tab",  # Tab
    "\x1b[Z": "key_backtab",  # Shift+Tab (backtab)
    "\x7f": "key_backspace",  # Backspace
    "\x08": "key_backspace",  # Backspace (alternate)
    "\x1b[3~": "key_delete",  # Delete
    # PA keys (using Ctrl combinations)
    "\x1b[1;5P": "pa1",  # Ctrl+F1
    "\x1b[1;5Q": "pa2",  # Ctrl+F2
    "\x1b[1;5R": "pa3",  # Ctrl+F3
    # Clear (Pause/Break or Ctrl+C alternative)
    "\x1b[2~": "clear",  # Insert key as Clear
    "\x03": "attn",  # Ctrl+C as ATTN
    # Escape to clear
    "\x1b\x1b": "clear",  # Double Escape as Clear
}


@dataclass
class TN3270Session:
    """A TN3270 terminal session."""

    session_id: str
    host: str
    port: int
    tnz: "tnz_module.Tnz"
    renderer: TN3270Renderer
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    connected: bool = False
    running_ast: AST | None = field(default=None, repr=False)
    _update_task: asyncio.Task | None = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)


class TN3270Manager:
    """Manages TN3270 terminal sessions."""

    def __init__(self, config: "TN3270Config", valkey: "ValkeyClient") -> None:
        self._config = config
        self._valkey = valkey
        self._sessions: dict[str, TN3270Session] = {}
        self._renderer = TN3270Renderer()

    async def start(self) -> None:
        """Start the TN3270 manager."""
        await self._valkey.subscribe_to_tn3270_control(self._handle_gateway_control)
        log.info(
            "TN3270 Manager started",
            default_host=self._config.host,
            default_port=self._config.port,
        )

    @property
    def session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def get_session(self, session_id: str) -> TN3270Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def create_session(
        self,
        session_id: str,
        host: str | None = None,
        port: int | None = None,
    ) -> TN3270Session:
        """Create a new TN3270 session."""
        # Check for existing session
        existing = self._sessions.get(session_id)
        if existing:
            log.info("Reusing existing TN3270 session", session_id=session_id)
            # Send current screen with field data
            await self._send_screen_update(existing)
            return existing

        if len(self._sessions) >= self._config.max_sessions:
            raise TerminalError(ErrorCodes.SESSION_LIMIT_REACHED, "Maximum TN3270 sessions reached")

        host = host or self._config.host
        port = port or self._config.port

        try:
            log.info(
                "Connecting to 3270 host",
                session_id=session_id,
                host=host,
                port=port,
            )

            # Create and connect tnz in a thread (it has its own event loop)
            loop = asyncio.get_running_loop()
            tnz = await loop.run_in_executor(
                _executor,
                self._create_tnz_connection,
                session_id,
                host,
                port,
            )

            session = TN3270Session(
                session_id=session_id,
                host=host,
                port=port,
                tnz=tnz,
                renderer=self._renderer,
                connected=True,
            )

            self._sessions[session_id] = session

            # Subscribe to TN3270 input channel
            sid = session_id
            await self._valkey.subscribe_to_tn3270_input(
                session_id, lambda data, s=sid: self._handle_input(s, data)
            )

            log.info(
                "Created TN3270 session",
                session_id=session_id,
                host=host,
                port=port,
            )

            # Send session created message
            msg = create_session_created_message(session_id, f"tn3270://{host}:{port}", 0)
            await self._valkey.publish_tn3270_output(session_id, serialize_message(msg))

            # Wait for initial screen data in thread (before starting update loop)
            await loop.run_in_executor(_executor, lambda: tnz.wait(timeout=2))

            # Send initial screen with field data
            await self._send_screen_update(session)

            # Now start update loop to poll for subsequent screen changes
            session._update_task = asyncio.create_task(self._update_loop(session))

            return session

        except Exception as e:
            log.exception("Failed to create TN3270 session", session_id=session_id)
            raise TerminalError(ErrorCodes.TERMINAL_CONNECTION_FAILED, str(e)) from e

    def _create_tnz_connection(
        self,
        session_id: str,
        host: str,
        port: int,
    ) -> "tnz_module.Tnz":
        """Create tnz connection in a thread (blocking)."""
        tnz = tnz_module.Tnz(name=session_id)

        # Always use IBM-3278-4-E (80x43) regardless of client screen size
        tnz.amaxcol = 80
        tnz.amaxrow = 43

        # Connect without TLS for Hercules
        tnz.connect(host=host, port=port, secure=False, verifycert=False)

        return tnz

    async def destroy_session(self, session_id: str, reason: str = "closed") -> None:
        """Destroy a TN3270 session."""
        session = self._sessions.pop(session_id, None)
        if not session:
            return

        # Signal stop and cancel update task
        session._stop_event.set()
        if session._update_task:
            session._update_task.cancel()
            try:
                await session._update_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from channels
        await self._valkey.unsubscribe_tn3270_session(session_id)

        # Close tnz connection in thread
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(_executor, session.tnz.close)
        except Exception:
            pass

        log.info("Destroyed TN3270 session", session_id=session_id, reason=reason)

        # Send session destroyed message
        msg = create_session_destroyed_message(session_id, reason)
        await self._valkey.publish_tn3270_output(session_id, serialize_message(msg))

    async def destroy_all_sessions(self) -> None:
        """Destroy all TN3270 sessions."""
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.destroy_session(session_id, "shutdown")

    async def _update_loop(self, session: TN3270Session) -> None:
        """Poll for screen updates and send them to the client."""
        tnz = session.tnz
        last_screen = ""
        loop = asyncio.get_running_loop()

        while not session._stop_event.is_set():
            try:
                # Wait for data with timeout in thread pool
                await loop.run_in_executor(_executor, lambda: tnz.wait(timeout=0.1))

                # Check if session lost
                if tnz.seslost:
                    log.info("TN3270 session lost", session_id=session.session_id)
                    await self.destroy_session(session.session_id, "connection_lost")
                    return

                # Check if screen updated
                if tnz.updated:
                    tnz.updated = False
                    session.last_activity = datetime.now()

                    # Send screen update with field data
                    await self._send_screen_update(session)

            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Update loop error", session_id=session.session_id)
                await asyncio.sleep(1)

    async def _handle_input(self, session_id: str, raw_data: str) -> None:
        """Handle keyboard input from the client."""
        session = self._sessions.get(session_id)
        if not session:
            return

        try:
            msg = parse_message(raw_data)
            if isinstance(msg, DataMessage):
                await self._process_input(session, msg.payload)
            elif isinstance(msg, ASTRunMessage):
                # Run AST as background task so we can still receive control messages
                asyncio.create_task(self._run_ast(session, msg.meta.ast_name, msg.meta.params))
            elif isinstance(msg, ASTControlMessage):
                await self._handle_ast_control(session, msg.meta.action)
        except Exception:
            log.exception("Handle input error", session_id=session_id)

    async def _handle_ast_control(self, session: TN3270Session, action: str) -> None:
        """Handle AST control commands (pause/resume/cancel)."""
        ast = session.running_ast
        log.info(
            "Handling AST control",
            action=action,
            session_id=session.session_id,
            has_ast=ast is not None,
        )
        if not ast:
            log.warning("No running AST to control", session_id=session.session_id)
            return

        if action == "pause":
            log.info("Pausing AST", session_id=session.session_id)
            ast.pause()
        elif action == "resume":
            log.info("Resuming AST", session_id=session.session_id)
            ast.resume()
        elif action == "cancel":
            log.info("Cancelling AST", session_id=session.session_id)
            ast.cancel()

    async def _run_ast(
        self,
        session: TN3270Session,
        ast_name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Run an AST (Automated Streamlined Transaction)."""
        # Check if there's already an AST running (including paused)
        if session.running_ast is not None:
            log.warning(
                "Cannot start AST - another AST is already running",
                ast_name=ast_name,
                session_id=session.session_id,
                running_ast=type(session.running_ast).__name__,
            )
            # Send error status to frontend
            status_msg = create_ast_status_message(
                session.session_id,
                ast_name,
                "failed",
                error="Another AST is already running. Please wait for it to complete, cancel it, or go to the History page to view its status.",
            )
            await self._valkey.publish_tn3270_output(
                session.session_id, serialize_message(status_msg)
            )
            return

        log.info("Running AST", ast_name=ast_name, session_id=session.session_id)

        # Generate unique execution_id for this AST run
        # session_id is used for WebSocket channel, execution_id is unique per run

        execution_id = str(uuid4())

        # Send running status
        status_msg = create_ast_status_message(
            session.session_id, ast_name, "running", message=f"Starting {ast_name}..."
        )
        await self._valkey.publish_tn3270_output(session.session_id, serialize_message(status_msg))

        # Get the event loop for thread-safe callbacks
        loop = asyncio.get_running_loop()

        # Create thread-safe progress callback
        def on_progress(
            current: int,
            total: int,
            current_item: str | None = None,
            item_status: (
                Literal["pending", "running", "success", "failed", "skipped"] | None
            ) = None,
            message: str | None = None,
        ) -> None:
            """Thread-safe progress callback."""
            progress_msg = create_ast_progress_message(
                session.session_id,
                execution_id,
                ast_name,
                current,
                total,
                current_item,
                item_status,
                message,
            )

            async def send():
                await self._valkey.publish_tn3270_output(
                    session.session_id, serialize_message(progress_msg)
                )

            asyncio.run_coroutine_threadsafe(send(), loop)

        # Create thread-safe item result callback
        def on_item_result(
            item_id: str,
            status: Literal["success", "failed", "skipped"],
            duration_ms: int | None = None,
            error: str | None = None,
            data: dict | None = None,
        ) -> None:
            """Thread-safe item result callback."""
            result_msg = create_ast_item_result_message(
                session.session_id,
                execution_id,
                item_id,
                status,
                duration_ms,
                error,
                data,
            )

            async def send():
                await self._valkey.publish_tn3270_output(
                    session.session_id, serialize_message(result_msg)
                )

            asyncio.run_coroutine_threadsafe(send(), loop)

        # Create thread-safe pause state callback
        def on_pause_state(paused: bool, message: str | None = None) -> None:
            """Thread-safe pause state callback."""
            log.info(
                "Pause state changed",
                paused=paused,
                message=message,
                session_id=session.session_id,
            )
            paused_msg = create_ast_paused_message(
                session.session_id,
                paused,
                message,
            )

            async def send():
                await self._valkey.publish_tn3270_output(
                    session.session_id, serialize_message(paused_msg)
                )
                # Also send a screen update so user sees current state while paused
                if paused:
                    await self._send_screen_update(session)

                # Update execution status in DynamoDB
                from ...db import get_dynamodb_client

                db = get_dynamodb_client()
                new_status = "paused" if paused else "running"
                db.update_execution(
                    session_id=session.session_id,
                    execution_id=execution_id,
                    updates={"status": new_status},
                )
                log.info(
                    "Updated execution status",
                    execution_id=execution_id,
                    status=new_status,
                )

            asyncio.run_coroutine_threadsafe(send(), loop)

        try:
            # Create Host wrapper for the session's tnz instance
            host = Host(session.tnz)

            # Get the appropriate AST
            if ast_name == "login":
                ast = LoginAST()
            else:
                raise ValueError(f"Unknown AST: {ast_name}")

            # Store the running AST in the session for control commands
            session.running_ast = ast

            # Set progress callbacks
            ast.set_callbacks(
                on_progress=on_progress,
                on_item_result=on_item_result,
                on_pause_state=on_pause_state,
            )

            # Run the AST in executor (blocking operations)
            # Pass execution_id so it matches what we store in DynamoDB
            result = await loop.run_in_executor(
                _executor,
                lambda: ast.run(host, execution_id=execution_id, **(params or {})),
            )

            # Clear the running AST
            session.running_ast = None

            # Send result status
            status_msg = create_ast_status_message(
                session.session_id,
                ast_name,
                result.status.value,
                message=result.message,
                error=result.error,
                duration=result.duration,
                data=result.data,
            )
            await self._valkey.publish_tn3270_output(
                session.session_id, serialize_message(status_msg)
            )

            # Update screen after AST completes
            await self._send_screen_update(session)

            log.info(
                "AST completed",
                ast_name=ast_name,
                status=result.status.value,
                duration=result.duration,
                session_id=session.session_id,
            )

        except Exception as e:
            # Clear the running AST on error
            session.running_ast = None

            log.exception("AST execution error", ast_name=ast_name, session_id=session.session_id)
            status_msg = create_ast_status_message(
                session.session_id,
                ast_name,
                "failed",
                error=str(e),
            )
            await self._valkey.publish_tn3270_output(
                session.session_id, serialize_message(status_msg)
            )

    async def _process_input(self, session: TN3270Session, data: str) -> None:
        """Process keyboard input and send to 3270 host."""
        tnz = session.tnz
        loop = asyncio.get_running_loop()

        try:
            # Check for special key sequences first
            for seq, action in KEY_MAPPINGS.items():
                if data.startswith(seq):
                    method = getattr(tnz, action, None)
                    if method:
                        log.debug("3270 key", action=action, session_id=session.session_id)
                        await loop.run_in_executor(_executor, method)
                        # Send updated screen after key
                        await self._send_screen_update(session)
                    return

            # Regular character input
            if data and data.isprintable():
                log.debug(
                    "3270 data",
                    data=repr(data),
                    session_id=session.session_id,
                )
                await loop.run_in_executor(_executor, lambda: tnz.key_data(data))
                await self._send_screen_update(session)

        except Exception as e:
            log.exception("Process input error", session_id=session.session_id)
            error_msg = create_error_message(
                session.session_id, ErrorCodes.TERMINAL_WRITE_FAILED, str(e)
            )
            await self._valkey.publish_tn3270_output(
                session.session_id, serialize_message(error_msg)
            )

    async def _send_screen_update(self, session: TN3270Session) -> None:
        """Send current screen to client with field information."""
        screen_data = self._renderer.render_screen_with_fields(session.tnz)

        # Convert renderer Field objects to TN3270Field model objects
        fields = [
            TN3270Field(
                start=f.start,
                end=f.end,
                protected=f.protected,
                intensified=f.intensified,
                row=f.row,
                col=f.col,
                length=f.length,
            )
            for f in screen_data.fields
        ]

        msg = create_tn3270_screen_message(
            session.session_id,
            screen_data.ansi,
            fields,
            screen_data.cursor_row,
            screen_data.cursor_col,
            screen_data.rows,
            screen_data.cols,
        )
        await self._valkey.publish_tn3270_output(session.session_id, serialize_message(msg))

    async def _handle_control(self, session_id: str, raw_data: str) -> None:
        """Handle control messages."""
        try:
            msg = parse_message(raw_data)

            if isinstance(msg, ResizeMessage):
                # 3270 doesn't really support dynamic resize
                # but we can acknowledge it
                log.debug(
                    "Resize ignored for 3270",
                    session_id=session_id,
                    cols=msg.meta.cols,
                    rows=msg.meta.rows,
                )
            elif isinstance(msg, SessionDestroyMessage):
                await self.destroy_session(session_id, "user_requested")

        except TerminalError as e:
            error_msg = create_error_message(session_id, e.code, e.message)
            await self._valkey.publish_tn3270_output(session_id, serialize_message(error_msg))
        except Exception:
            log.exception("Handle control error", session_id=session_id)

    async def _handle_gateway_control(self, raw_data: str) -> None:
        """Handle global gateway control messages (session creation)."""
        try:
            msg = parse_message(raw_data)

            if isinstance(msg, SessionCreateMessage):
                meta = msg.meta
                # Extract host/port from session create meta
                # Could be passed as shell="host:port" or in env
                host = None
                port = None
                if meta and meta.shell:
                    if ":" in meta.shell:
                        host, port_str = meta.shell.rsplit(":", 1)
                        try:
                            port = int(port_str)
                        except ValueError:
                            pass
                    else:
                        host = meta.shell

                await self.create_session(
                    msg.session_id,
                    host=host,
                    port=port,
                )

        except TerminalError as e:
            try:
                parsed = parse_message(raw_data)
                if hasattr(parsed, "session_id"):
                    error_msg = create_error_message(parsed.session_id, e.code, e.message)
                    await self._valkey.publish_tn3270_output(
                        parsed.session_id, serialize_message(error_msg)
                    )
            except Exception:
                pass
            log.warning("TN3270 gateway control error", error=str(e))
        except Exception:
            log.exception("Handle TN3270 gateway control error")


# Singleton instance
_manager: TN3270Manager | None = None


def get_tn3270_manager() -> TN3270Manager:
    """Get the singleton TN3270 manager."""
    if _manager is None:
        raise RuntimeError("TN3270 manager not initialized")
    return _manager


def init_tn3270_manager(config: "TN3270Config", valkey: "ValkeyClient") -> TN3270Manager:
    """Initialize and return the TN3270 manager."""
    global _manager
    _manager = TN3270Manager(config, valkey)
    return _manager
