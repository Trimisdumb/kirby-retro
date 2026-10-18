"""Chiptune synthétisée en Python et jouée en boucle par un lecteur du système.

Le WAV est généré une seule fois dans le cache, puis confié à mpv, ffplay,
paplay, aplay ou sox (winsound sur Windows). S'il n'y a pas de lecteur
disponible, on reste simplement silencieux.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import threading
import wave
from array import array
from pathlib import Path
from typing import Any

from .config import cache_dir

RATE = 11025
BPM = 128.0

# Am · F · C · G (fondamentale MIDI)
CHORDS = [("Am", 57), ("F", 53), ("C", 60), ("G", 55)]
MELODY = {
    57: [69, 72, 76, 72, 69, 76, 72, 71],
    53: [65, 69, 72, 69, 65, 72, 69, 67],
    60: [72, 76, 79, 76, 72, 79, 76, 74],
    55: [67, 71, 74, 71, 67, 74, 71, 69],
}


def _hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def music_file() -> Path:
    return cache_dir() / "chiptune.wav"


def ensure_chiptune() -> Path | None:
    """Génère (une fois) la boucle chiptune dans le cache et la retourne."""
    path = music_file()
    if path.is_file() and path.stat().st_size > 4096:
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _synth_to(path)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def _synth_to(path: Path) -> None:
    beat = 60.0 / BPM
    step = beat / 2.0  # croche
    bars = 8
    total = int(RATE * bars * 4 * beat)
    buf = array("h", bytes(total * 2))
    seed = 0x2F6E2B1

    def noise() -> float:
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        return (seed / 0x3FFFFFFF) - 1.0

    def tone(t0: float, dur: float, freq: float, amp: float, kind: str, decay: float) -> None:
        i0 = int(t0 * RATE)
        n = int(dur * RATE)
        for i in range(n):
            idx = i0 + i
            if idx >= total:
                break
            phase = (i * freq / RATE) % 1.0
            if kind == "pulse":
                v = 1.0 if phase < 0.25 else -1.0
            elif kind == "square":
                v = 1.0 if phase < 0.5 else -1.0
            else:  # triangle
                v = 4.0 * abs(phase - 0.5) - 1.0
            buf[idx] += int(amp * math.exp(-decay * i / RATE) * v * 10000)

    for bar in range(bars):
        _name, root = CHORDS[bar % 4]
        t_bar = bar * 4 * beat
        # mélodie (pulse 25 %) — croches
        for k, midi in enumerate(MELODY[root]):
            tone(t_bar + k * step, step * 1.05, _hz(midi), 0.34, "pulse", 6.5)
        # basse (triangle) — noires
        for k in range(4):
            midi = root - 12 if k in (0, 2) else root - 5
            tone(t_bar + k * beat, beat * 0.9, _hz(midi), 0.5, "triangle", 2.2)
        # charley (bruit) — contretemps
        for k in range(4):
            i0 = int((t_bar + (k + 0.5) * beat) * RATE)
            n = int(0.045 * RATE)
            for i in range(n):
                idx = i0 + i
                if idx >= total:
                    break
                buf[idx] += int(0.12 * math.exp(-70.0 * i / RATE) * noise() * 10000)
        # grosse caisse — temps 1 et 3
        for k in (0, 2):
            i0 = int((t_bar + k * beat) * RATE)
            n = int(0.11 * RATE)
            for i in range(n):
                idx = i0 + i
                if idx >= total:
                    break
                f = 38.0 + 120.0 * math.exp(-18.0 * i / RATE)
                buf[idx] += int(
                    0.45 * math.exp(-30.0 * i / RATE) * math.sin(2 * math.pi * f * i / RATE) * 10000
                )

    # fondu de boucle (clic de raccord)
    fade = int(0.012 * RATE)
    for i in range(min(fade, total // 2)):
        buf[i] = int(buf[i] * i / fade)
        buf[total - 1 - i] = int(buf[total - 1 - i] * i / fade)

    # saturation puis écriture WAV (16 bits mono)
    for i in range(total):
        v = buf[i]
        if v > 31000:
            buf[i] = 31000
        elif v < -31000:
            buf[i] = -31000
    if sys.byteorder == "big":
        buf.byteswap()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(buf.tobytes())


class MusicPlayer:
    """Lit la chiptune en boucle avec un lecteur du système (silence si aucun)."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.enabled = bool(config.get("music", True))
        self.path: Path | None = None
        self.kind: str | None = None
        self.problem: str | None = None
        self.prepare_done = False
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # préparation (à lancer dans un thread)
    def prepare(self) -> None:
        try:
            custom = str(self.config.get("music_file") or "").strip()
            if custom:
                p = Path(custom).expanduser()
                self.path = p if p.is_file() else None
                if self.path is None:
                    self.problem = f"fichier musique introuvable : {custom}"
            else:
                self.path = ensure_chiptune()
                if self.path is None:
                    self.problem = "génération de la chiptune impossible"
            self.kind = self._find_player()
            if self.kind is None and self.problem is None:
                self.problem = "aucun lecteur audio trouvé"
        finally:
            self.prepare_done = True

    @property
    def usable(self) -> bool:
        return bool(self.path and self.kind)

    def _find_player(self) -> str | None:
        if not self.path:
            return None
        if sys.platform == "win32":
            return "winsound" if self.path.suffix.lower() == ".wav" else None
        if sys.platform == "darwin":
            return "afplay" if shutil.which("afplay") else None
        for exe, kind in (
            ("mpv", "mpv"),
            ("ffplay", "ffplay"),
            ("paplay", "paplay"),
            ("aplay", "aplay"),
            ("play", "sox"),
        ):
            if shutil.which(exe):
                return kind
        return None

    def _cmd(self) -> list[str] | None:
        p = str(self.path)
        if self.kind == "mpv":
            return ["mpv", "--no-video", "--quiet", "--loop-file=inf", "--volume=45", p]
        if self.kind == "ffplay":
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", "45", "-loop", "0", p]
        if self.kind == "afplay":
            return ["afplay", p]
        if self.kind == "paplay":
            return ["paplay", p]
        if self.kind == "aplay":
            return ["aplay", "-q", p]
        if self.kind == "sox":
            return ["play", "-q", p]
        return None

    # lecture
    def start(self) -> None:
        if not self.enabled or not self.usable:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        if self.kind == "winsound":
            try:
                import winsound

                winsound.PlaySound(
                    str(self.path),
                    winsound.SND_FILENAME | winsound.SND_LOOP | winsound.SND_ASYNC,
                )
                self._stop.wait()
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:  # noqa: BLE001
                pass
            return
        native_loop = self.kind in ("mpv", "ffplay")
        while not self._stop.is_set():
            cmd = self._cmd()
            if not cmd:
                return
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError:
                self.problem = f"lecteur « {self.kind} » introuvable"
                return
            self._proc.wait()
            self._proc = None
            if self._stop.is_set():
                return
            if native_loop:
                self.problem = "le lecteur s'est arrêté"
                return
            if self._stop.wait(0.2):
                return

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except OSError:
                    pass
        self._proc = None

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if self.enabled:
            self.start()
        else:
            self.stop()
        return self.enabled

    def close(self) -> None:
        self.enabled = False
        self.stop()
