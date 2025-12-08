"""Coverage for simple model modules (data, error, ping, session, types)."""

from __future__ import annotations

import sys
import importlib
import unittest

import src.models as models_package
import src.models.types as types_module


class _fresh_module:
    """Context manager to import a module fresh and restore the original afterwards."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.original = sys.modules.get(name)
        parent_name, _, child = name.rpartition(".")
        self.parent_name = parent_name or None
        self.child = child or None
        self.parent_module = sys.modules.get(parent_name) if parent_name else None

    def __enter__(self):
        if self.original is not None:
            sys.modules.pop(self.name, None)
        module = importlib.import_module(self.name)
        self.new_module = module
        return module

    def __exit__(self, exc_type, exc, tb):
        sys.modules.pop(self.name, None)
        if self.original is not None:
            sys.modules[self.name] = self.original
            if self.parent_module and self.child:
                setattr(self.parent_module, self.child, self.original)
        else:
            if self.parent_module and self.child and hasattr(self.parent_module, self.child):
                delattr(self.parent_module, self.child)
        return False


class ModelsSimpleModuleTests(unittest.TestCase):
    """Exercise modules that otherwise only define data structures."""

    def test_data_message_factory(self) -> None:
        with _fresh_module("src.models.data") as module:
            msg = module.create_data_message("sess-data", "payload")
            self.assertEqual(msg.session_id, "sess-data")
            self.assertEqual(msg.payload, "payload")
            self.assertIsNone(msg.meta)
            dumped = msg.model_dump(by_alias=True)
            self.assertEqual(dumped["sessionId"], "sess-data")

    def test_error_message_factory_and_meta(self) -> None:
        with _fresh_module("src.models.error") as module:
            msg = module.create_error_message("sess-err", "E42", "boom")
            self.assertEqual(msg.meta.code, "E42")
            self.assertEqual(msg.payload, "boom")
            self.assertIsNone(msg.meta.details)

    def test_ping_and_pong_messages_have_meta(self) -> None:
        with _fresh_module("src.models.ping") as module:
            ping = module.PingMessage(sessionId="sess-ping")
            pong = module.PongMessage(sessionId="sess-pong")
            self.assertEqual(ping.type, types_module.MessageType.PING)
            self.assertEqual(pong.type, types_module.MessageType.PONG)
            self.assertIsNone(ping.meta)
            self.assertIsNone(pong.meta)

    def test_session_message_factories_and_aliases(self) -> None:
        with _fresh_module("src.models.session") as module:
            create_meta = module.SessionCreateMeta(shell="tn3270", cols=80, rows=24)
            create_msg = module.SessionCreateMessage(sessionId="sess-create", meta=create_meta)
            self.assertEqual(create_msg.meta.cols, 80)

            destroyed_msg = module.create_session_destroyed_message("sess-end", "done")
            self.assertEqual(destroyed_msg.payload, "done")
            self.assertIsNone(destroyed_msg.meta.exit_code)
            dumped = destroyed_msg.meta.model_dump(by_alias=True)
            self.assertIn("exitCode", dumped)

            created_msg = module.create_session_created_message("sess-new", "bash", 1234)
            self.assertEqual(created_msg.meta.shell, "bash")
            self.assertEqual(created_msg.meta.pid, 1234)

    def test_message_type_enum_and_envelope(self) -> None:
        with _fresh_module("src.models.types") as module:
            enum_values = {member.value for member in module.MessageType}
            expected = {
                "data",
                "ping",
                "pong",
                "error",
                "session.create",
                "session.destroy",
                "session.created",
                "session.destroyed",
                "tn3270.screen",
                "tn3270.cursor",
                "ast.run",
                "ast.control",
                "ast.status",
                "ast.paused",
            }
            self.assertTrue(expected.issubset(enum_values))
            self.assertIn("DataMessage", module.MessageEnvelope)
            self.assertIn("TN3270ScreenMessage", module.MessageEnvelope)

    def test_models_package_exports(self) -> None:
        with _fresh_module("src.models") as module:
            exports = set(module.__all__)
            for name in [
                "BaseMessage",
                "DataMessage",
                "PingMessage",
                "SessionCreateMessage",
                "TN3270Field",
                "MessageType",
                "parse_message",
            ]:
                self.assertIn(name, exports)
                self.assertTrue(hasattr(module, name))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

