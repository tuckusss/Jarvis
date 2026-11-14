"""Offline-first behaviour, local path security and fallback semantics."""
import io
import json
import sys
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from jarvis.agent import Agent
from jarvis.config import Config
from jarvis.local_ai import LocalRuntime
from jarvis.memory import Memory
from jarvis.tools import ToolExecutor, local_command
from jarvis.voice import transcribe_local, SAMPLE_RATE


class OfflineTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.memory = Memory(Path(self.tmp.name) / "db.sqlite")
        self.config = Config()
        self.google = MagicMock()
        self.permits = []
        self.executor = ToolExecutor(self.config, self.memory, self.google,
                                     lambda n, d: self.permits.append(n) or False,
                                     lambda: "screen not used")

    def tearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    def test_local_is_default_no_cloud_key_required(self):
        self.assertEqual(self.config.provider, "local")
        self.assertFalse(self.config.wake_enabled)

    def test_direct_local_app_command_uses_only_allowlisted_tool(self):
        with patch("jarvis.tools.platform.system", return_value="Windows"), \
             patch("jarvis.tools.subprocess.Popen") as popen:
            response = local_command("Hey Jarvis, open notepad", self.executor)
        self.assertEqual(response, "Opened notepad.")
        popen.assert_called_once()

    def test_local_instructions_do_not_route_to_shell(self):
        self.assertIsNone(local_command("Jarvis, run powershell to erase the disk", self.executor))

    def test_local_note_requires_human_permission(self):
        result = local_command("Remember that my favourite colour is blue", self.executor)
        self.assertIn("denied", result)
        self.assertEqual(self.permits, ["remember_note"])

    def test_local_shortcut_does_not_load_llm(self):
        agent = Agent(self.config, self.memory, self.executor)
        agent.local_runtime.client = MagicMock(side_effect=AssertionError("LLM should not run"))
        response = agent.ask("Jarvis show my reminders")
        self.assertIn("reminders", response.lower())

    def test_no_cloud_fallback_in_local_mode(self):
        agent = Agent(self.config, self.memory, self.executor)
        agent.local_runtime.client = MagicMock(side_effect=RuntimeError("model missing"))
        with self.assertRaisesRegex(RuntimeError, "Offline AI unavailable"):
            agent.ask("Explain what a CPU is")

    def test_hybrid_fallback_only_when_explicitly_configured(self):
        self.config.provider = "hybrid"
        agent = Agent(self.config, self.memory, self.executor)
        agent.local_runtime.client = MagicMock(side_effect=RuntimeError("model unavailable"))
        agent._ask_cloud = MagicMock(return_value="Cloud result")
        with patch("jarvis.agent.api_key", return_value="test-token"):
            self.assertEqual(agent.ask("Explain gravity"), "Cloud result")
        agent._ask_cloud.assert_called_once()

    def test_local_chat_uses_loopback_client_and_persists_answer(self):
        agent = Agent(self.config, self.memory, self.executor)
        fake = MagicMock()
        fake.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None, content="Local answer"))]
        )
        agent.local_runtime.client = MagicMock(return_value=fake)
        self.assertEqual(agent.ask("What is photosynthesis?"), "Local answer")
        self.assertEqual(self.memory.recent()[-1]["content"], "Local answer")
        self.assertEqual(fake.chat.completions.create.call_count, 1)

    def test_bundled_model_required_before_local_runtime_start(self):
        runtime = LocalRuntime()
        with patch("jarvis.local_ai.has_local_bundle", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "missing"):
                runtime.client()

    def test_offline_vosk_transcription_reads_wav_data(self):
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(b'\x00' * 8000)
        recognizer = MagicMock()
        recognizer.AcceptWaveform.return_value = False
        recognizer.FinalResult.return_value = json.dumps({"text": "open notepad"})
        with patch.dict(sys.modules, {"vosk": SimpleNamespace(KaldiRecognizer=MagicMock(return_value=recognizer))}), \
             patch("jarvis.voice._local_vosk_model", return_value=object()):
            result = transcribe_local(buffer.getvalue(), "mock-model")
        self.assertEqual(result, "open notepad")
        recognizer.AcceptWaveform.assert_called()
