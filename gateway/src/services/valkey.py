# ============================================================================
# Async Valkey Client
# ============================================================================

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import redis.asyncio as redis
import structlog

from ..core import (
    GATEWAY_CONTROL_CHANNEL,
    TN3270_CONTROL_CHANNEL,
    ValkeyConfig,
    get_pty_control_channel,
    get_pty_input_channel,
    get_pty_output_channel,
    get_tn3270_input_channel,
    get_tn3270_output_channel,
)

log = structlog.get_logger()


class ValkeyClient:
    """Async Valkey/Redis client for PTY and TN3270 communication."""

    def __init__(self, config: ValkeyConfig) -> None:
        self._config = config
        self._publisher: redis.Redis | None = None  # type: ignore[type-arg]
        self._subscriber: redis.Redis | None = None  # type: ignore[type-arg]
        self._pubsub: redis.client.PubSub | None = None
        self._handlers: dict[str, Callable[[str], Coroutine[Any, Any, None]]] = {}
        self._running = False
        self._listen_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Connect to Valkey."""
        url = f"redis://{self._config.host}:{self._config.port}/{self._config.db}"
        if self._config.password:
            url = f"redis://:{self._config.password}@{self._config.host}:{self._config.port}/{self._config.db}"

        self._publisher = redis.from_url(url, decode_responses=True)
        self._subscriber = redis.from_url(url, decode_responses=True)
        self._pubsub = self._subscriber.pubsub()

        # Test connection
        await self._publisher.ping()
        log.info("Connected to Valkey", host=self._config.host, port=self._config.port)

    async def disconnect(self) -> None:
        """Disconnect from Valkey."""
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.close()
        if self._publisher:
            await self._publisher.close()
        if self._subscriber:
            await self._subscriber.close()

        log.info("Disconnected from Valkey")

    async def subscribe_to_gateway_control(
        self,
        handler: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to the global gateway control channel for PTY session creation."""
        self._handlers[GATEWAY_CONTROL_CHANNEL] = handler

        if self._pubsub:
            await self._pubsub.subscribe(GATEWAY_CONTROL_CHANNEL)
            log.info(
                "Subscribed to gateway control channel", channel=GATEWAY_CONTROL_CHANNEL
            )

    async def subscribe_to_tn3270_control(
        self,
        handler: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to the TN3270 gateway control channel for session creation."""
        self._handlers[TN3270_CONTROL_CHANNEL] = handler

        if self._pubsub:
            await self._pubsub.subscribe(TN3270_CONTROL_CHANNEL)
            log.info(
                "Subscribed to TN3270 control channel",
                channel=TN3270_CONTROL_CHANNEL,
            )

    async def subscribe_to_input(
        self,
        session_id: str,
        handler: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to input channel for a session."""
        channel = get_pty_input_channel(session_id)
        self._handlers[channel] = handler

        if self._pubsub:
            await self._pubsub.subscribe(channel)
            log.debug("Subscribed to input", session_id=session_id, channel=channel)

    async def subscribe_to_control(
        self,
        session_id: str,
        handler: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to control channel for a session."""
        channel = get_pty_control_channel(session_id)
        self._handlers[channel] = handler

        if self._pubsub:
            await self._pubsub.subscribe(channel)
            log.debug("Subscribed to control", session_id=session_id, channel=channel)

    async def unsubscribe_session(self, session_id: str) -> None:
        """Unsubscribe from all channels for a session."""
        input_channel = get_pty_input_channel(session_id)
        control_channel = get_pty_control_channel(session_id)

        if self._pubsub:
            await self._pubsub.unsubscribe(input_channel, control_channel)

        self._handlers.pop(input_channel, None)
        self._handlers.pop(control_channel, None)

        log.debug("Unsubscribed session", session_id=session_id)

    async def unsubscribe_tn3270_session(self, session_id: str) -> None:
        """Unsubscribe from all TN3270 channels for a session."""
        input_channel = get_tn3270_input_channel(session_id)

        if self._pubsub:
            await self._pubsub.unsubscribe(input_channel)

        self._handlers.pop(input_channel, None)

        log.debug("Unsubscribed TN3270 session", session_id=session_id)

    async def subscribe_to_tn3270_input(
        self,
        session_id: str,
        handler: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to TN3270 input channel for a session."""
        channel = get_tn3270_input_channel(session_id)
        self._handlers[channel] = handler

        if self._pubsub:
            await self._pubsub.subscribe(channel)
            log.debug(
                "Subscribed to TN3270 input", session_id=session_id, channel=channel
            )

    async def publish_output(self, session_id: str, data: str) -> None:
        """Publish output to a session's PTY output channel."""
        if not self._publisher:
            return

        channel = get_pty_output_channel(session_id)
        await self._publisher.publish(channel, data)

    async def publish_tn3270_output(self, session_id: str, data: str) -> None:
        """Publish output to a session's TN3270 output channel."""
        if not self._publisher:
            return

        channel = get_tn3270_output_channel(session_id)
        await self._publisher.publish(channel, data)

    async def start_listening(self) -> None:
        """Start listening for messages."""
        self._running = True
        self._listen_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        """Main listen loop for pubsub messages."""
        if not self._pubsub:
            return

        while self._running:
            try:
                # Only try to get messages if we have handlers (subscriptions)
                if not self._handlers:
                    await asyncio.sleep(0.1)
                    continue

                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.1
                )
                if message and message["type"] == "message":
                    channel: str = message["channel"]
                    data: str = message["data"]

                    handler = self._handlers.get(channel)
                    if handler:
                        try:
                            await handler(data)
                        except Exception:
                            log.exception("Handler error", channel=channel)

            except asyncio.CancelledError:
                break
            except redis.ConnectionError:
                log.warning("Valkey connection lost, reconnecting...")
                await asyncio.sleep(1)
            except Exception:
                log.exception("Listen loop error")
                await asyncio.sleep(1)


# Singleton instance
_client: ValkeyClient | None = None


def get_valkey_client() -> ValkeyClient:
    """Get the singleton Valkey client."""
    if _client is None:
        raise RuntimeError("Valkey client not initialized")
    return _client


async def init_valkey_client(config: ValkeyConfig) -> ValkeyClient:
    """Initialize and return the Valkey client."""
    global _client
    _client = ValkeyClient(config)
    await _client.connect()
    # Note: start_listening() should be called after initial subscriptions are set up
    return _client


async def close_valkey_client() -> None:
    """Close the Valkey client."""
    global _client
    if _client:
        await _client.disconnect()
        _client = None
