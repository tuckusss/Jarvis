"""Streaming voice integration tests without audio hardware or cloud access."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from jarvis.agent import Agent
from jarvis.config import Config
from jarvis.memory import Memory


class AgentStreamingTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.memory = Memory(Path(self.tmp.name) / "messages.sqlite")
        self.config = Config()
        self.executor = MagicMock()
        self.agent = Agent(self.config, self.memory, self.executor)
        self.api = MagicMock()
        self.agent.local_runtime.client = MagicMock(return_value=self.api)

    def tearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    def test_sends_first_sentence_before_response_is_complete(self):
        chunks = ["JARVIS is ", "ready. ", "How can I help you today?"]
        events = [
            SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=chunk)
            )]) for chunk in chunks
        ]
        self.api.chat.completions.create.return_value = iter(events)
        spoken = []
        result = self.agent.ask_stream("Say hello to me", spoken.append)
        self.assertEqual(result, "".join(chunks))
        self.assertEqual(spoken, ["JARVIS is ready.", "How can I help you today?"])
        self.assertEqual(self.memory.recent()[-1]["content"], result)
        self.assertTrue(self.api.chat.completions.create.call_args.kwargs["stream"])
        self.assertNotIn("tools", self.api.chat.completions.create.call_args.kwargs)

    def test_actionable_requests_are_not_streamed_without_tool_policy(self):
        self.agent.ask = MagicMock(return_value="Opened notepad.")
        got = []
        result = self.agent.ask_stream("Open notepad", got.append)
        self.assertEqual(result, "Opened notepad.")
        self.agent.ask.assert_called_once_with("Open notepad")
        self.assertEqual(got, [])
        self.api.chat.completions.create.assert_not_called()

    def test_no_streaming_when_user_selected_cloud(self):
        self.config.provider = "openai"
        self.agent.ask = MagicMock(return_value="Cloud response.")
        self.assertEqual(self.agent.ask_stream("Hello", lambda _: None), "Cloud response.")
        self.agent.ask.assert_called_once()

    def test_empty_stream_fails_closed(self):
        self.api.chat.completions.create.return_value = iter([])
        with self.assertRaisesRegex(RuntimeError, "empty streaming"):
            self.agent.ask_stream("Say hello", lambda _: None)
