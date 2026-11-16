from threading import Event
from unittest import TestCase

from jarvis.request_control import RequestCancelled, check_cancelled, should_cancel


class RequestControlTests(TestCase):
    def test_open_request(self):
        event = Event()
        self.assertFalse(should_cancel(event))
        check_cancelled(event)
        check_cancelled(None)

    def test_cancelled_request(self):
        event = Event()
        event.set()
        self.assertTrue(should_cancel(event))
        with self.assertRaises(RequestCancelled):
            check_cancelled(event)
