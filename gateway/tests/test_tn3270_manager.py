"""Tests for the TN3270 session manager."""

from __future__ import annotations

import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from src.core import TN3270Config, TerminalError
from src.services.tn3270.manager import TN3270Manager


class _StubTnz:
    """Minimal tnz stub used for manager tests."""

    def __init__(self) -> None:
        self.seslost = False
        self.updated = False

    def wait(self, timeout: float | None = None) -> None:  # pragma: no cover - synchronous stub
        return None

    def close(self) -> None:  # pragma: no cover - synchronous stub
        return None


class _FakeValkey:
    """Valkey stub collecting manager interactions."""

    def __init__(self) -> None:
        self.subscribe_to_tn3270_control = AsyncMock()
        self.subscribe_to_tn3270_input = AsyncMock()
        self.unsubscribe_tn3270_session = AsyncMock()
        self.publish_tn3270_output = AsyncMock()


class TN3270ManagerTests(IsolatedAsyncioTestCase):
    """Covers session lifecycle behaviors of the manager."""

    def setUp(self) -> None:
        self.config = TN3270Config(host="localhost", port=23, max_sessions=2)
        self.valkey = _FakeValkey()
        self.manager = TN3270Manager(self.config, self.valkey)  # type: ignore[arg-type]

    async def asyncTearDown(self) -> None:
        # Ensure any background tasks are shut down between tests
        for session_id, session in list(self.manager._sessions.items()):
            if hasattr(session, "session_id"):
                await self.manager.destroy_session(session_id)
            else:
                self.manager._sessions.pop(session_id, None)

    async def test_start_subscribes_to_control_channel(self) -> None:
        await self.manager.start()
        self.valkey.subscribe_to_tn3270_control.assert_awaited_once()

    async def test_create_session_initializes_state_and_channels(self) -> None:
        stub_tnz = _StubTnz()
        with patch.object(
            TN3270Manager,
            "_create_tnz_connection",
            return_value=stub_tnz,
        ), patch.object(
            TN3270Manager,
            "_send_screen_update",
            new=AsyncMock(),
        ) as mock_screen, patch.object(
            TN3270Manager,
            "_update_loop",
            new=AsyncMock(),
        ) as mock_update:
            session = await self.manager.create_session("session-1")
            await session._update_task  # type: ignore[union-attr]

        self.assertEqual(self.manager.session_count, 1)
        self.valkey.subscribe_to_tn3270_input.assert_awaited_once()
        self.valkey.publish_tn3270_output.assert_awaited()
        mock_screen.assert_awaited()
        mock_update.assert_awaited()

    async def test_destroy_session_unsubscribes_and_cleans_up(self) -> None:
        stub_tnz = _StubTnz()
        with patch.object(TN3270Manager, "_create_tnz_connection", return_value=stub_tnz), patch.object(
            TN3270Manager, "_send_screen_update", new=AsyncMock()
        ), patch.object(TN3270Manager, "_update_loop", new=AsyncMock(return_value=None)):
            session = await self.manager.create_session("session-2")
            await session._update_task  # type: ignore[union-attr]

        await self.manager.destroy_session("session-2", reason="test")

        self.valkey.unsubscribe_tn3270_session.assert_awaited_once_with("session-2")
        self.assertEqual(self.manager.session_count, 0)

    async def test_create_session_enforces_maximum_limit(self) -> None:
        self.manager._sessions["existing"] = object()  # Simulate max_sessions == 2 with one entry
        self.manager._sessions["existing-2"] = object()

        with self.assertRaises(TerminalError):
            await self.manager.create_session("third")


if __name__ == "__main__":
    unittest.main()
