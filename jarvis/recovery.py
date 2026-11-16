"""Opt-in Windows Error Reporting application restart registration.

Windows may offer to restart the process after an unhandled crash or hang.
It is not a persistent service or a guarantee of recovery, and does not
bypass Windows login or elevate permissions.
"""
from __future__ import annotations
from dataclasses import dataclass
import ctypes
import os


@dataclass(frozen=True)
class RecoveryStatus:
    enabled: bool
    registered: bool
    detail: str


def register_windows_restart(enabled: bool = True, *, kernel32=None,
                             os_name: str | None = None) -> RecoveryStatus:
    if not enabled:
        return RecoveryStatus(False, False, "Disabled in JARVIS Settings")
    platform = os_name if os_name is not None else os.name
    if platform != "nt":
        return RecoveryStatus(True, False, "Windows application recovery is unavailable")
    try:
        native = kernel32 if kernel32 is not None else ctypes.windll.kernel32
        fn = native.RegisterApplicationRestart
        if kernel32 is None:
            fn.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong]
            fn.restype = ctypes.c_long
        # Passing null command line retains normal startup arguments.
        result = fn(None, 0)
        return RecoveryStatus(True, result == 0,
                              "Windows recovery registered" if result == 0
                              else "Windows declined recovery registration")
    except (OSError, AttributeError, ValueError, TypeError):
        return RecoveryStatus(True, False, "Windows recovery API unavailable")
