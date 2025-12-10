"""Additional coverage for TN3270 manager internals."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.ast import ASTResult, ASTStatus
from src.core import TN3270Config, TerminalError
from src.models import (
    ASTControlMessage,
    ASTControlMeta,
    DataMessage,
    SessionCreateMessage,
    SessionDestroyMessage,
    serialize_message,
)
from src.services.tn3270.manager import KEY_MAPPINGS, TN3270Manager, TN3270Session


class _StubValkey:
    def __init__(self) -> None:
        self.subscribe_to_tn3270_control = AsyncMock()
        self.subscribe_to_tn3270_input = AsyncMock()
        self.unsubscribe_tn3270_session = AsyncMock()
        self.publish_tn3270_output = AsyncMock()


class _StubTnz:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.pf1 = lambda: self.calls.append("pf1")

        def key_data(value: str) -> None:
            self.calls.append(f"data:{value}")

        self.key_data = key_data


class ManagerExtendedTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.config = TN3270Config(host="localhost", port=23, max_sessions=2)
        self.valkey = _StubValkey()
        self.manager = TN3270Manager(self.config, self.valkey)  # type: ignore[arg-type]

    async def test_handle_ast_control_with_and_without_ast(self) -> None:
        session = TN3270Session(
            session_id="sess",
            host="h",
            port=23,
            tnz=SimpleNamespace(),
            renderer=self.manager._renderer,
            connected=True,
        )
        self.manager._sessions["sess"] = session

        await self.manager._handle_ast_control(session, "pause")
        self.assertIsNone(session.running_ast)

        fake_ast = MagicMock()
        session.running_ast = fake_ast
        await self.manager._handle_ast_control(session, "pause")
        fake_ast.pause.assert_called_once()
        await self.manager._handle_ast_control(session, "resume")
        fake_ast.resume.assert_called_once()
        await self.manager._handle_ast_control(session, "cancel")
        fake_ast.cancel.assert_called_once()

    async def test_process_input_handles_keys_and_data(self) -> None:
        tnz = _StubTnz()
        session = TN3270Session(
            session_id="sess",
            host="h",
            port=23,
            tnz=tnz,
            renderer=self.manager._renderer,
            connected=True,
        )
        self.manager._sessions["sess"] = session

        with patch.object(self.manager, "_send_screen_update", new=AsyncMock()):
            await self.manager._process_input(session, next(iter(KEY_MAPPINGS.keys())))
            self.assertIn("pf1", tnz.calls)
            await self.manager._process_input(session, "ABC")
            self.assertIn("data:ABC", tnz.calls)

    async def test_handle_gateway_control_success_and_error(self) -> None:
        payload = SessionCreateMessage(sessionId="abc", meta={"shell": "host:50"})
        with patch(
            "src.services.tn3270.manager.parse_message", return_value=payload
        ), patch.object(self.manager, "create_session", new=AsyncMock()) as mock_create:
            await self.manager._handle_gateway_control("raw")
        mock_create.assert_awaited_once_with("abc", host="host", port=50)

        error = TerminalError("E1", "fail")
        second_payload = SimpleNamespace(session_id="abc")
        with patch(
            "src.services.tn3270.manager.parse_message",
            side_effect=[error, second_payload],
        ), patch.object(
            self.valkey, "publish_tn3270_output", new=AsyncMock()
        ) as mock_publish:
            await self.manager._handle_gateway_control("broken")
        mock_publish.assert_awaited()

    async def test_handle_input_routes_messages(self) -> None:
        session = TN3270Session(
            session_id="sess",
            host="h",
            port=23,
            tnz=_StubTnz(),
            renderer=self.manager._renderer,
            connected=True,
        )
        self.manager._sessions["sess"] = session

        from src.models import DataMessage

        data_msg = DataMessage(sessionId="sess", payload="ABC")
        with patch(
            "src.services.tn3270.manager.parse_message", return_value=data_msg
        ), patch.object(
            self.manager, "_process_input", new=AsyncMock()
        ) as mock_process:
            await self.manager._handle_input("sess", "raw")
        mock_process.assert_awaited_once()

        destroy_msg = SessionDestroyMessage(sessionId="sess")
        with patch(
            "src.services.tn3270.manager.parse_message", return_value=destroy_msg
        ), patch.object(
            self.manager, "destroy_session", new=AsyncMock()
        ) as mock_destroy:
            await self.manager._handle_input("sess", "raw")
        mock_destroy.assert_awaited_once_with("sess", "user_requested")

        ctrl_msg = ASTControlMessage(
            sessionId="sess", meta=ASTControlMeta(action="pause")
        )
        with patch(
            "src.services.tn3270.manager.parse_message", return_value=ctrl_msg
        ), patch.object(
            self.manager, "_handle_ast_control", new=AsyncMock()
        ) as mock_control:
            await self.manager._handle_input("sess", "raw")
        mock_control.assert_awaited_once()

    async def test_create_session_reuses_existing_session(self) -> None:
        stub_session = TN3270Session(
            session_id="reuse",
            host="h",
            port=23,
            tnz=_StubTnz(),
            renderer=self.manager._renderer,
            connected=True,
        )
        self.manager._sessions["reuse"] = stub_session
        with patch.object(
            self.manager, "_send_screen_update", new=AsyncMock()
        ) as mock_send:
            result = await self.manager.create_session("reuse")
        self.assertIs(result, stub_session)
        mock_send.assert_awaited_once()
        self.assertEqual(self.valkey.subscribe_to_tn3270_input.await_count, 0)

    async def test_handle_input_ignores_unknown_session(self) -> None:
        data_msg = DataMessage(sessionId="missing", payload="ABC")
        with patch(
            "src.services.tn3270.manager.parse_message", return_value=data_msg
        ), patch.object(
            self.manager, "_process_input", new=AsyncMock()
        ) as mock_process:
            await self.manager._handle_input("missing", "raw")
        mock_process.assert_not_awaited()

    async def test_process_input_handles_exception(self) -> None:
        class BoomTnz(_StubTnz):
            def __init__(self) -> None:
                super().__init__()

                def boom(value: str) -> None:
                    raise RuntimeError("boom")

                self.key_data = boom  # type: ignore[assignment]

        session = TN3270Session(
            session_id="sess",
            host="h",
            port=23,
            tnz=BoomTnz(),
            renderer=self.manager._renderer,
            connected=True,
        )
        self.manager._sessions["sess"] = session
        self.valkey.publish_tn3270_output.reset_mock()
        with patch.object(self.manager, "_send_screen_update", new=AsyncMock()):
            await self.manager._process_input(session, "ABC")
        self.assertGreaterEqual(self.valkey.publish_tn3270_output.await_count, 1)

    async def test_handle_control_destroy_and_errors(self) -> None:
        destroy_msg = SessionDestroyMessage(sessionId="sess")
        with patch(
            "src.services.tn3270.manager.parse_message", return_value=destroy_msg
        ), patch.object(
            self.manager, "destroy_session", new=AsyncMock()
        ) as mock_destroy:
            await self.manager._handle_control("sess", "raw")
        mock_destroy.assert_awaited_once_with("sess", "user_requested")

        with patch(
            "src.services.tn3270.manager.parse_message",
            side_effect=TerminalError("E", "fail"),
        ), patch.object(
            self.valkey, "publish_tn3270_output", new=AsyncMock()
        ) as mock_publish:
            await self.manager._handle_control("sess", "raw")
        mock_publish.assert_awaited()

    async def test_destroy_session_handles_missing(self) -> None:
        await self.manager.destroy_session("missing")
        self.assertEqual(self.valkey.unsubscribe_tn3270_session.await_count, 0)

    async def test_destroy_session_cleans_up_resources(self) -> None:
        tnz = SimpleNamespace(close=lambda: None)
        session = TN3270Session(
            session_id="sess-destroy",
            host="h",
            port=23,
            tnz=tnz,
            renderer=self.manager._renderer,
            connected=True,
        )
        session._stop_event = threading.Event()
        session._update_task = asyncio.create_task(asyncio.sleep(0))
        self.manager._sessions["sess-destroy"] = session

        await self.manager.destroy_session("sess-destroy", reason="done")

        self.valkey.unsubscribe_tn3270_session.assert_awaited_once_with("sess-destroy")
        self.assertNotIn("sess-destroy", self.manager._sessions)

    async def test_run_ast_prevents_parallel_runs(self) -> None:
        session = TN3270Session(
            session_id="sess",
            host="h",
            port=23,
            tnz=_StubTnz(),
            renderer=self.manager._renderer,
            connected=True,
        )
        placeholder_ast = MagicMock()
        session.running_ast = placeholder_ast
        self.valkey.publish_tn3270_output.reset_mock()
        await self.manager._run_ast(session, "login", {})
        self.assertIs(session.running_ast, placeholder_ast)
        self.assertGreaterEqual(self.valkey.publish_tn3270_output.await_count, 1)

    async def test_run_ast_executes_successfully(self) -> None:
        class StubAST:
            name = "login"

            def __init__(self) -> None:
                self.callbacks: dict[str, tuple] = {}

            def set_callbacks(
                self, on_progress=None, on_item_result=None, on_pause_state=None
            ):
                self.callbacks = {
                    "on_progress": on_progress,
                    "on_item_result": on_item_result,
                    "on_pause_state": on_pause_state,
                }

            def run(self, host, execution_id: str, **kwargs):
                if self.callbacks["on_progress"]:
                    self.callbacks["on_progress"](1, 2, "item", "running", "msg")
                if self.callbacks["on_item_result"]:
                    self.callbacks["on_item_result"]("item", "success", 10, None, {})
                return ASTResult(status=ASTStatus.SUCCESS, message="ok")

        class FakeLoop:
            async def run_in_executor(self, executor, func, *args, **kwargs):
                return func(*args, **kwargs)

        session = TN3270Session(
            session_id="sess",
            host="h",
            port=23,
            tnz=_StubTnz(),
            renderer=self.manager._renderer,
            connected=True,
        )

        with patch("src.services.tn3270.manager.Host", return_value=MagicMock()), patch(
            "src.services.tn3270.manager.LoginAST", return_value=StubAST()
        ), patch("src.services.tn3270.manager.uuid4", return_value="exec-1"), patch(
            "src.services.tn3270.manager.asyncio.get_running_loop",
            return_value=FakeLoop(),
        ), patch(
            "src.services.tn3270.manager.asyncio.run_coroutine_threadsafe",
            side_effect=lambda coro, loop: asyncio.create_task(coro),
        ), patch.object(
            self.manager, "_send_screen_update", new=AsyncMock()
        ):
            self.valkey.publish_tn3270_output.reset_mock()
            await self.manager._run_ast(session, "login", {"foo": "bar"})

        self.assertGreaterEqual(self.valkey.publish_tn3270_output.await_count, 2)
        self.assertIsNone(session.running_ast)

    async def test_run_ast_unknown_name_raises(self) -> None:
        session = TN3270Session(
            session_id="sess",
            host="h",
            port=23,
            tnz=_StubTnz(),
            renderer=self.manager._renderer,
            connected=True,
        )
        self.valkey.publish_tn3270_output.reset_mock()
        await self.manager._run_ast(session, "unknown", {})
        self.assertGreaterEqual(self.valkey.publish_tn3270_output.await_count, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
