from unittest import TestCase
from unittest.mock import MagicMock
from jarvis.recovery import register_windows_restart


class RecoveryTests(TestCase):
    def test_not_windows(self):
        s = register_windows_restart(os_name="posix")
        self.assertFalse(s.registered)

    def test_disabled_never_calls_native_api(self):
        native = MagicMock()
        s = register_windows_restart(False, kernel32=native, os_name="nt")
        self.assertFalse(s.enabled)
        native.RegisterApplicationRestart.assert_not_called()

    def test_success(self):
        native = MagicMock()
        native.RegisterApplicationRestart.return_value = 0
        s = register_windows_restart(kernel32=native, os_name="nt")
        self.assertTrue(s.registered)
        native.RegisterApplicationRestart.assert_called_once_with(None, 0)

    def test_failed_native_restart_is_not_success(self):
        native = MagicMock()
        native.RegisterApplicationRestart.return_value = 3
        self.assertFalse(register_windows_restart(
            kernel32=native, os_name="nt").registered)
