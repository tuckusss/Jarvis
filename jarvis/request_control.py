"""Cooperative cancellation for JARVIS voice, model and tool requests.

Cancellation never undoes actions already committed. It prevents future
actions and stops streaming presentation as soon as the worker observes it.
"""
from __future__ import annotations

import threading


class RequestCancelled(RuntimeError):
    """A user stopped the current conversation request."""


def check_cancelled(event: threading.Event | None) -> None:
    if event is not None and event.is_set():
        raise RequestCancelled("Request cancelled by owner")


def should_cancel(event: threading.Event | None) -> bool:
    return bool(event is not None and event.is_set())
