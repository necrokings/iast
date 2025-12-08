"""Tests for core channel helpers."""

from __future__ import annotations

import importlib
import unittest

import src.core.channels as channels


class ChannelHelperTests(unittest.TestCase):
    """Ensure channel naming helpers follow the documented pattern."""

    @classmethod
    def setUpClass(cls) -> None:
        importlib.reload(channels)

    def test_input_channel_pattern(self) -> None:
        self.assertEqual(
            channels.get_tn3270_input_channel("sess-1"), "tn3270.input.sess-1"
        )

    def test_output_channel_pattern(self) -> None:
        self.assertEqual(
            channels.get_tn3270_output_channel("sess-99"), "tn3270.output.sess-99"
        )

    def test_control_channel_constant(self) -> None:
        self.assertEqual(channels.TN3270_CONTROL_CHANNEL, "tn3270.control")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

