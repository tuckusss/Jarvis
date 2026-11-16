"""Request cancellation must stop future tool actions and suppress results."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from jarvis.agent import Agent
from jarvis.config import Config
from jarvis.memory import Memory
from jarvis.request_control import RequestCancelled
from jarvis.tools import ToolExecutor


class CancellationTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.memory = Memory(Path(self.tmp.name) / "memory.db")
        self.cfg = Config()
        self.google = MagicMock()
        self.approvals = []
        self.exec = ToolExecutor(
            self.cfg, self.memory, self.google,
            lambda name, preview: self.approvals.append(name) or True,
            lambda: "safe screen",
        )
        self.agent = Agent(self.cfg, self.memory, self.exec)
        self.fake = MagicMock()
        self.agent.local_runtime.client = MagicMock(return_value=self.fake)

    def tearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    def test_stream_cancellation_stops_before_second_sentence(self):
        request = Event()
        chunks = ["First sentence. ", "Second sentence. "]
        events = iter([
            SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=x))]) for x in chunks
        ])
        self.fake.chat.completions.create.return_value = events
        heard = []
        def on_sentence(sentence):
            heard.append(sentence)
            request.set()
        with self.assertRaises(RequestCancelled):
            self.agent.ask_stream("Just say two sentences", on_sentence, cancel_event=request)
        self.assertEqual(heard, ["First sentence."])
        self.assertEqual(self.memory.recent(), [])

    def test_cancelled_tool_does_not_run_after_approval(self):
        request = Event()
        def approve(name, detail):
            request.set()
            return True
        self.exec.approve = approve
        with self.exec.authorised_request(None, cancel_event=request):
            result = self.exec.execute("remember_note", {"note": "Never save this"})
        self.assertIn("locked", result["error"].lower())
        self.assertEqual(self.memory.recall(), [])

    def test_local_cancellation_is_not_routed_to_cloud(self):
        request = Event()
        self.cfg.provider = "hybrid"
        self.agent._ask_local = MagicMock(side_effect=RequestCancelled("Owner cancelled"))
        self.agent._ask_cloud = MagicMock(return_value="should never happen")
        from unittest.mock import patch
        with patch("jarvis.agent.api_key", return_value="test-key"):
            with self.assertRaises(RequestCancelled):
                self.agent.ask("Explain weather patterns", cancel_event=request)
        self.agent._ask_cloud.assert_not_called()

    def test_cloud_response_cannot_trigger_tool_after_cancel(self):
        request = Event()
        self.cfg.provider = "openai"
        fake_cloud = MagicMock()
        function_call = SimpleNamespace(type="function_call", name="remember_note",
              arguments='{"note":"Unauthorized note"}', call_id="call1")
        def response(**kwargs):
            request.set()
            return SimpleNamespace(output=[function_call], output_text="")
        fake_cloud.responses.create.side_effect = response
        self.agent.client = fake_cloud
        with self.assertRaises(RequestCancelled):
            self.agent.ask("Remember this fact", cancel_event=request)
        self.assertEqual(self.memory.recall(), [])
        self.assertEqual(self.approvals, [])
