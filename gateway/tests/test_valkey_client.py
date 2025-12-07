"""Tests for the asynchronous Valkey/Redis client."""

from __future__ import annotations

import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from src.core import (
    TN3270_CONTROL_CHANNEL,
    ValkeyConfig,
    get_tn3270_input_channel,
    get_tn3270_output_channel,
)
from src.services import valkey as valkey_module
from src.services.valkey import (
    ValkeyClient,
    close_valkey_client,
    get_valkey_client,
    init_valkey_client,
)


class ValkeyClientTests(IsolatedAsyncioTestCase):
    """Exercise the Valkey client without a live Redis server."""

    def setUp(self) -> None:
        self.config = ValkeyConfig(host="valkey", port=6380, db=2, password=None)
        self.from_url_patcher = patch("src.services.valkey.redis.from_url")
        self.mock_from_url = self.from_url_patcher.start()
        self.addCleanup(self.from_url_patcher.stop)

        self.publisher = MagicMock()
        self.publisher.ping = AsyncMock()
        self.publisher.publish = AsyncMock()
        self.publisher.close = AsyncMock()

        self.subscriber = MagicMock()
        self.subscriber.close = AsyncMock()

        self.pubsub = MagicMock()
        self.pubsub.subscribe = AsyncMock()
        self.pubsub.unsubscribe = AsyncMock()
        self.pubsub.close = AsyncMock()
        self.subscriber.pubsub.return_value = self.pubsub

        self.mock_from_url.side_effect = [self.publisher, self.subscriber]

        valkey_module._client = None

    def tearDown(self) -> None:
        valkey_module._client = None

    async def test_connect_initializes_clients_and_pings(self) -> None:
        client = ValkeyClient(self.config)
        await client.connect()

        self.publisher.ping.assert_awaited_once()
        self.assertIsNotNone(client._publisher)
        self.assertIsNotNone(client._subscriber)
        self.assertIs(client._pubsub, self.pubsub)

        self.mock_from_url.assert_any_call("redis://valkey:6380/2", decode_responses=True)

    async def test_connect_with_password_uses_auth_url(self) -> None:
        config = ValkeyConfig(host="valkey", port=6380, db=2, password="secret")
        client = ValkeyClient(config)

        await client.connect()

        first_call_url = self.mock_from_url.call_args_list[0].args[0]
        self.assertEqual(first_call_url, "redis://:secret@valkey:6380/2")

    async def test_subscribe_to_control_channel_tracks_handler(self) -> None:
        client = ValkeyClient(self.config)
        client._pubsub = self.pubsub
        handler = AsyncMock()

        await client.subscribe_to_tn3270_control(handler)

        self.pubsub.subscribe.assert_awaited_once_with(TN3270_CONTROL_CHANNEL)
        self.assertIn(TN3270_CONTROL_CHANNEL, client._handlers)
        self.assertIs(client._handlers[TN3270_CONTROL_CHANNEL], handler)

    async def test_subscribe_to_input_channel_uses_session_channel(self) -> None:
        client = ValkeyClient(self.config)
        client._pubsub = self.pubsub
        handler = AsyncMock()

        await client.subscribe_to_tn3270_input("session-1", handler)

        channel = get_tn3270_input_channel("session-1")
        self.pubsub.subscribe.assert_awaited_once_with(channel)
        self.assertIs(client._handlers[channel], handler)

    async def test_unsubscribe_tn3270_session_removes_handler(self) -> None:
        client = ValkeyClient(self.config)
        client._pubsub = self.pubsub
        channel = get_tn3270_input_channel("session-1")
        client._handlers[channel] = AsyncMock()

        await client.unsubscribe_tn3270_session("session-1")

        self.pubsub.unsubscribe.assert_awaited_once_with(channel)
        self.assertNotIn(channel, client._handlers)

    async def test_publish_tn3270_output_targets_output_channel(self) -> None:
        client = ValkeyClient(self.config)
        client._publisher = self.publisher

        await client.publish_tn3270_output("session-2", "payload")

        channel = get_tn3270_output_channel("session-2")
        self.publisher.publish.assert_awaited_once_with(channel, "payload")

    async def test_init_and_close_valkey_client_singleton(self) -> None:
        with patch.object(ValkeyClient, "connect", new_callable=AsyncMock) as mock_connect, patch.object(
            ValkeyClient, "disconnect", new_callable=AsyncMock
        ) as mock_disconnect:
            client = await init_valkey_client(self.config)

            mock_connect.assert_awaited_once()
            self.assertIs(client, get_valkey_client())

            await close_valkey_client()
            mock_disconnect.assert_awaited_once()

            with self.assertRaises(RuntimeError):
                get_valkey_client()


if __name__ == "__main__":
    unittest.main()

