"""Audio-device discovery and diagnostics. Input is only captured on user request."""
from __future__ import annotations

def input_devices(query=None) -> list[tuple[int, str]]:
    """List microphones without opening streams or recording any audio."""
    if query is None:
        import sounddevice as sd
        query = sd.query_devices
    try:
        devices = query()
        return [
            (index, str(device.get("name", f"Microphone {index}")))
            for index, device in enumerate(devices)
            if int(device.get("max_input_channels", 0)) > 0
        ]
    except Exception:
        return []

def microphone_probe(device: int | None = None) -> dict:
    """Read just enough microphone RMS to diagnose an explicitly selected input.

    Returns amplitude only; no samples are retained, saved, or uploaded.
    """
    import numpy as np
    import sounddevice as sd
    with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16",
                           blocksize=1600, device=device) as stream:
        rms = []
        for _ in range(5):
            frame, overflow = stream.read(1600)
            v = np.frombuffer(bytes(frame), dtype=np.int16).astype(np.float32)
            rms.append(float(np.sqrt(np.mean(v * v))))
    return {"device": device, "rms": round(sum(rms) / len(rms), 1),
            "usable": True}
