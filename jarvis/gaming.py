"""Local, read-only detection of supported games for a low-impact JARVIS mode.

No account, telemetry upload, game injection, or anti-cheat interactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

SUPPORTED_GAMES = {
    "ck3.exe": "Crusader Kings III",
    "ck3game.exe": "Crusader Kings III",
    "mb_warband.exe": "Mount & Blade: Warband",
    "warband.exe": "Mount & Blade: Warband",
    "mb_warband_napoleonic.exe": "Mount & Blade: Warband",
}


@dataclass(frozen=True)
class GamingState:
    active: bool
    title: str = ""
    process: str = ""


def detect_game(process_names: Iterable[str]) -> GamingState:
    for raw in process_names:
        name = raw.strip().casefold()
        if name in SUPPORTED_GAMES:
            return GamingState(True, SUPPORTED_GAMES[name], name)
    return GamingState(False)


def installed_game_running() -> GamingState:
    """Inspect process names only; never launch a game or read its memory."""
    try:
        import psutil
        names = []
        for proc in psutil.process_iter(attrs=["name"], ad_value=""):
            try:
                name = proc.info.get("name") or ""
                names.append(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
        return detect_game(names)
    except Exception:
        return GamingState(False)


def select_inference_threads(cpus: int, *, gaming: bool) -> int:
    """Reserve CPU for games without preventing local AI entirely."""
    ordinary = min(max(2, cpus - 2), 6)
    if gaming:
        return min(ordinary, 2)
    return ordinary
