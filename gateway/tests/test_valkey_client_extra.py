"""Extra coverage for Valkey client helpers."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from src.core import ValkeyConfig
from src.services.valkey import ValkeyClient


class FakePubSub:
    def __init__(self) -> None:
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)

    async def unsubscribe(self, channel: str) -> None:
        self.unsubscribed.append(channel)

    async def close(self) -> None:
        self.closed = True

    async def get_message(self, **_: object):
        await asyncio.sleep(0)
        return None


class FakeRedis:
    def __init__(self) -> None:
        self.ping = AsyncMock()
        self.close = AsyncMock()
        self._pubsub = FakePubSub()

    def pubsub(self) -> FakePubSub:
        return self._pubsub


class ValkeyClientTests(unittest.IsolatedAsyncioTestCase):
    """Ensure the async Valkey client wires redis connections correctly."""

    async def test_connect_uses_password_and_tests_connection(self) -> None:
        config = ValkeyConfig(host="host", port=6380, db=2, password="pw")
        client = ValkeyClient(config)

        publisher = FakeRedis()
        subscriber = FakeRedis()

        with patch("src.services.valkey.redis.from_url", side_effect=[publisher, subscriber]) as from_url:
            await client.connect()

        expected_url = "redis://:pw@host:6380/2"
        from_url.assert_any_call(expected_url, decode_responses=True)
        publisher.ping.assert_awaited_once()
        self.assertIsNotNone(client._pubsub)

    async def test_subscribe_and_unsubscribe_manage_handlers(self) -> None:
        client = ValkeyClient(ValkeyConfig())
        client._pubsub = FakePubSub()

        async def handler(_: str) -> None:
            return None

        await client.subscribe_to_tn3270_input("sess", handler)
        channel = "tn3270.input.sess"
        self.assertIn(channel, client._handlers)
        self.assertIn(channel, client._pubsub.subscribed)  # type: ignore[union-attr]

        await client.unsubscribe_tn3270_session("sess")
        self.assertNotIn(channel, client._handlers)
        self.assertIn(channel, client._pubsub.unsubscribed)  # type: ignore[union-attr]

    async def test_publish_noop_without_publisher(self) -> None:
        client = ValkeyClient(ValkeyConfig())
        await client.publish_tn3270_output("sess", "data")  # Should not raise

    async def test_disconnect_cancels_listener_and_closes_clients(self) -> None:
        client = ValkeyClient(ValkeyConfig())
        client._publisher = FakeRedis()
        client._subscriber = FakeRedis()
        client._pubsub = FakePubSub()
        client._listen_task = asyncio.create_task(asyncio.sleep(1))
        client._running = True

        await client.disconnect()

        self.assertFalse(client._running)
        self.assertTrue(client._pubsub.closed)  # type: ignore[union-attr]
        client._publisher.close.assert_awaited_once()  # type: ignore[union-attr]
        client._subscriber.close.assert_awaited_once()  # type: ignore[union-attr]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

