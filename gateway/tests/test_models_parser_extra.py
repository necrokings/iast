"""Additional coverage for message parser helpers."""

from __future__ import annotations

import json
import unittest

import src.models.ast as ast_module
import src.models.data as data_module
import src.models.error as error_module
import src.models.ping as ping_module
import src.models.session as session_module
import src.models.parser as parser_module


class ParserTests(unittest.TestCase):
    """Cover the parser entrypoints for multiple message types."""

    def test_parse_data_message_from_string(self) -> None:
        raw = data_module.DataMessage(sessionId="sess", payload="hello").model_dump_json(
            by_alias=True
        )
        parsed = parser_module.parse_message(raw)
        self.assertIsInstance(parsed, data_module.DataMessage)
        self.assertEqual(parsed.payload, "hello")

    def test_parse_ast_run_from_bytes(self) -> None:
        message = ast_module.ASTRunMessage(
            sessionId="sess",
            meta=ast_module.ASTRunMeta(astName="login", params={"foo": "bar"}),
        )
        parsed = parser_module.parse_message(message.model_dump_json(by_alias=True).encode())
        self.assertIsInstance(parsed, ast_module.ASTRunMessage)
        self.assertEqual(parsed.meta.ast_name, "login")

    def test_parse_ast_control_message(self) -> None:
        message = ast_module.ASTControlMessage(
            sessionId="sess",
            meta=ast_module.ASTControlMeta(action="pause"),
        )
        parsed = parser_module.parse_message(message.model_dump_json(by_alias=True))
        self.assertIsInstance(parsed, ast_module.ASTControlMessage)
        self.assertEqual(parsed.meta.action, "pause")

    def test_serialize_message_uses_aliases(self) -> None:
        message = ast_module.ASTRunMessage(
            sessionId="sess", meta=ast_module.ASTRunMeta(astName="login")
        )
        serialized = parser_module.serialize_message(message)
        data = json.loads(serialized)
        self.assertEqual(data["sessionId"], "sess")
        self.assertEqual(data["meta"]["astName"], "login")

    def test_parse_unknown_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            parser_module.parse_message(json.dumps({"type": "unknown"}))

    def test_parse_additional_message_types(self) -> None:
        messages = [
            ping_module.PingMessage(sessionId="sess"),
            ping_module.PongMessage(sessionId="sess"),
            error_module.ErrorMessage(
                sessionId="sess",
                payload="fail",
                meta=error_module.ErrorMeta(code="E1"),
            ),
            session_module.SessionCreateMessage(sessionId="sess"),
            session_module.SessionDestroyMessage(sessionId="sess"),
            session_module.SessionCreatedMessage(
                sessionId="sess", meta=session_module.SessionCreatedMeta(shell="bash")
            ),
            session_module.SessionDestroyedMessage(
                sessionId="sess",
                meta=session_module.SessionDestroyedMeta(exitCode=0),
            ),
        ]

        for message in messages:
            raw = message.model_dump_json(by_alias=True)
            parsed = parser_module.parse_message(raw)
            self.assertIsInstance(parsed, type(message))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

