"""Local, user-scoped DPAPI encryption for opted-in JARVIS project notes.

Windows DPAPI protects bytes using the current Windows sign-in identity.
It does NOT protect against malware already acting as that Windows user.
Never silently substitute cleartext, base64 or a machine-wide key.
"""
from __future__ import annotations

import ctypes
import os

CRYPTPROTECT_UI_FORBIDDEN = 0x01
ENTROPY = b"JARVIS private project memory 0.9"


class WindowsDpapi:
    def __init__(self, crypt32=None, kernel32=None, os_name=None):
        platform = os_name if os_name is not None else os.name
        if platform != "nt":
            raise OSError("Project vault requires Windows DPAPI; refusing plaintext fallback")
        if crypt32 is None:
            crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        if kernel32 is None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.crypt32 = crypt32
        self.kernel32 = kernel32

        class DataBlob(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.c_ulong),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]
        self.Blob = DataBlob

        for function in (self.crypt32.CryptProtectData, self.crypt32.CryptUnprotectData):
            function.restype = ctypes.c_int
            function.argtypes = [
                ctypes.POINTER(DataBlob), ctypes.c_wchar_p,
                ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                ctypes.c_ulong, ctypes.POINTER(DataBlob),
            ] if function is self.crypt32.CryptProtectData else [
                ctypes.POINTER(DataBlob), ctypes.c_void_p,
                ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                ctypes.c_ulong, ctypes.POINTER(DataBlob),
            ]
        self.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel32.LocalFree.restype = ctypes.c_void_p

    def _blob(self, value: bytes):
        buffer = ctypes.create_string_buffer(value, max(1, len(value)))
        return self.Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer

    def _call(self, data: bytes, *, decrypt: bool) -> bytes:
        if not isinstance(data, bytes) or not data:
            raise ValueError("Project memory cipher input must contain bytes")
        in_blob, hold_input = self._blob(data)
        entropy_blob, hold_entropy = self._blob(ENTROPY)
        out_blob = self.Blob()
        if decrypt:
            result = self.crypt32.CryptUnprotectData(
                ctypes.byref(in_blob), None, ctypes.byref(entropy_blob),
                None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
            )
        else:
            result = self.crypt32.CryptProtectData(
                ctypes.byref(in_blob), "JARVIS private project note",
                ctypes.byref(entropy_blob), None, None,
                CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
            )
        if not result:
            raise OSError(ctypes.get_last_error(), "Windows DPAPI could not process project note")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            self.kernel32.LocalFree(ctypes.cast(out_blob.pbData, ctypes.c_void_p))

    def encrypt(self, text: str) -> bytes:
        return self._call(text.encode("utf-8"), decrypt=False)

    def decrypt(self, value: bytes) -> str:
        return self._call(value, decrypt=True).decode("utf-8")
