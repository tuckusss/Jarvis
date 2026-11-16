from unittest import TestCase
from jarvis.audio_devices import input_devices

class AudioDeviceTests(TestCase):
    def test_input_device_filter(self):
        def query():
            return [
                {"name":"Speakers", "max_input_channels":0},
                {"name":"Headset mic", "max_input_channels":1},
                {"name":"USB condenser mic", "max_input_channels":2},
            ]
        self.assertEqual(input_devices(query), [(1,"Headset mic"),(2,"USB condenser mic")])

    def test_query_fail_does_not_crash_settings(self):
        def bad_query():
            raise RuntimeError("audio host unavailable")
        self.assertEqual(input_devices(bad_query), [])
