"""Tests for the gateway application entrypoints."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import src.app as app_module


class AppAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_main_initializes_components(self) -> None:
        config = SimpleNamespace(
            valkey=SimpleNamespace(host="valkey", port=6379),
            tn3270=SimpleNamespace(host="host", port=23, max_sessions=2),
            dynamodb=SimpleNamespace(),
        )
        fake_valkey = SimpleNamespace(start_listening=AsyncMock())
        fake_manager = SimpleNamespace(start=AsyncMock())
        fake_loop = SimpleNamespace(add_signal_handler=lambda *args, **kwargs: None)

        with patch.object(app_module, "get_config", return_value=config), patch(
            "src.db.get_dynamodb_client"
        ) as mock_db, patch.object(
            app_module, "init_valkey_client", new=AsyncMock(return_value=fake_valkey)
        ) as mock_valkey, patch.object(
            app_module, "init_tn3270_manager", return_value=fake_manager
        ) as mock_manager, patch.object(
            app_module.asyncio, "get_running_loop", return_value=fake_loop
        ):
            task = asyncio.create_task(app_module.async_main())
            await asyncio.sleep(0)
            assert app_module._shutdown_event is not None
            app_module._shutdown_event.set()
            await task

        mock_db.assert_called_once_with(config.dynamodb)
        mock_valkey.assert_awaited_once()
        mock_manager.assert_called_once_with(config.tn3270, fake_valkey)
        fake_manager.start.assert_awaited_once()
        fake_valkey.start_listening.assert_awaited_once()
        app_module._shutdown_event = None

    async def test_shutdown_handles_manager_and_valkey(self) -> None:
        fake_manager = SimpleNamespace(destroy_all_sessions=AsyncMock())
        with patch.object(app_module, "get_tn3270_manager", return_value=fake_manager), patch.object(
            app_module, "close_valkey_client", new=AsyncMock()
        ) as mock_close:
            app_module._shutdown_event = asyncio.Event()
            await app_module.shutdown()

        fake_manager.destroy_all_sessions.assert_awaited_once()
        mock_close.assert_awaited_once()
        assert app_module._shutdown_event is not None
        self.assertTrue(app_module._shutdown_event.is_set())
        app_module._shutdown_event = None

    def test_main_runs_async_main(self) -> None:
        def fake_run(coro):
            coro.close()

        with patch.object(app_module.asyncio, "run", side_effect=fake_run) as mock_run:
            app_module.main()

        mock_run.assert_called_once()

    def test_main_handles_keyboard_interrupt(self) -> None:
        async def fake_shutdown():
            fake_shutdown.called = True  # type: ignore[attr-defined]

        async def fake_async_main():
            fake_async_main.called = True  # type: ignore[attr-defined]

        def fake_run(coro):
            if not hasattr(fake_run, "times"):
                fake_run.times = 0  # type: ignore[attr-defined]
            fake_run.times += 1  # type: ignore[attr-defined]
            if fake_run.times == 1:
                coro.close()
                raise KeyboardInterrupt
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(coro)
            finally:
                loop.close()

        with patch.object(app_module, "shutdown", new=fake_shutdown), patch.object(
            app_module, "async_main", new=fake_async_main
        ), patch.object(app_module.asyncio, "run", side_effect=fake_run) as mock_run:
            fake_shutdown.called = False  # type: ignore[attr-defined]
            app_module.main()

        self.assertEqual(mock_run.call_count, 2)
        self.assertTrue(fake_shutdown.called)  # type: ignore[attr-defined]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

