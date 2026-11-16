from unittest import TestCase
from unittest.mock import MagicMock
from jarvis.local_ai import LocalRuntime

class RuntimeStatusTests(TestCase):
    def test_unstarted_does_not_start_automatically(self):
        runtime = LocalRuntime()
        status = runtime.status_snapshot()
        self.assertEqual(status["state"], "not started")
        self.assertTrue(status["loopback_only"])

    def test_running_and_exited_are_visible(self):
        runtime = LocalRuntime()
        runtime._launch_count = 2
        runtime.proc = MagicMock()
        runtime.proc.poll.return_value = None
        self.assertEqual(runtime.status_snapshot()["state"], "running")
        runtime.proc.poll.return_value = 2
        state = runtime.status_snapshot()
        self.assertIn("recovers on next request", state["state"])
        self.assertEqual(state["recoveries"], 1)
