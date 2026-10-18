"""Détection automatique de RetroArch et des émulateurs natifs."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .cores import NATIVE_HINTS, RETROARCH_CORES

FLATPAK_ID = "org.libretro.RetroArch"


def which(name: str) -> str | None:
    return shutil.which(name)


def _windows_retroarch_candidates() -> list[Path]:
    roots = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "USERPROFILE"):
        val = os.environ.get(key)
        if val:
            roots.append(Path(val))
    roots.append(Path.home())
    roots.append(Path("C:/"))
    names = [
        "RetroArch/retroarch.exe",
        "RetroArch-Win64/retroarch.exe",
        "Steam/steamapps/common/RetroArch/retroarch.exe",
        "Programs/RetroArch/retroarch.exe",
    ]
    out: list[Path] = []
    for root in roots:
        for name in names:
            out.append(root / name)
    # RetroArch « portable » à côté du launcher (dossier retroarch/ ou exe direct)
    launcher_dir = Path(__file__).resolve().parent.parent
    out.append(launcher_dir / "retroarch" / "retroarch.exe")
    out.append(launcher_dir / "retroarch.exe")
    return out


def _linux_retroarch_candidates() -> list[Path]:
    home = Path.home()
    return [
        Path("/usr/bin/retroarch"),
        Path("/usr/local/bin/retroarch"),
        home / ".local/bin/retroarch",
        home / "Applications/RetroArch.AppImage",
        Path("/snap/bin/retroarch"),
    ]


def _macos_retroarch_candidates() -> list[Path]:
    return [
        Path("/Applications/RetroArch.app/Contents/MacOS/RetroArch"),
        Path.home() / "Applications/RetroArch.app/Contents/MacOS/RetroArch",
    ]


def find_flatpak_retroarch() -> str | None:
    """Retourne « flatpak run org.libretro.RetroArch » si le Flatpak est installé."""
    if sys.platform in ("win32", "darwin"):
        return None
    for base in (Path("/var/lib/flatpak/app"), Path.home() / ".local/share/flatpak/app"):
        if (base / FLATPAK_ID).is_dir():
            return f"flatpak run {FLATPAK_ID}"
    flatpak = which("flatpak")
    if not flatpak:
        return None
    try:
        done = subprocess.run(
            [flatpak, "info", FLATPAK_ID],
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode == 0:
        return f"flatpak run {FLATPAK_ID}"
    return None


def find_retroarch() -> str | None:
    w = which("retroarch")
    if w:
        return w
    flatpak = find_flatpak_retroarch()
    if flatpak:
        return flatpak
    candidates: list[Path]
    if sys.platform == "win32":
        candidates = _windows_retroarch_candidates()
    elif sys.platform == "darwin":
        candidates = _macos_retroarch_candidates()
    else:
        candidates = _linux_retroarch_candidates()
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def is_flatpak(retroarch_path: str | None) -> bool:
    return bool(retroarch_path) and retroarch_path.strip().startswith("flatpak")


def retroarch_executable_ok(retroarch_path: str | None) -> bool:
    """Vrai si la cible RetroArch existe (fichier local ou Flatpak disponible)."""
    value = (retroarch_path or "").strip()
    if not value:
        return False
    if is_flatpak(value):
        return bool(which("flatpak"))
    return Path(value).is_file()


def flatpak_cores_dir() -> Path:
    return Path.home() / ".var/app/org.libretro.RetroArch/config/retroarch/cores"


def retroarch_cfg_candidates() -> list[Path]:
    home = Path.home()
    return [
        home / ".config/retroarch/retroarch.cfg",
        home / ".var/app/org.libretro.RetroArch/config/retroarch/retroarch.cfg",
        home / ".retroarch/retroarch.cfg",
        home / "snap/retroarch/current/.config/retroarch/retroarch.cfg",
    ]


def cfg_libretro_directory() -> Path | None:
    """Dossier de cores déclaré par RetroArch lui-même (retroarch.cfg → libretro_directory)."""
    for cfg in retroarch_cfg_candidates():
        try:
            text = cfg.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "libretro_directory":
                value = value.strip().strip('"')
                if value:
                    path = Path(os.path.expandvars(value)).expanduser()
                    if path.is_dir():
                        return path
    return None


def cores_dirs(retroarch_path: str | None = None) -> list[Path]:
    """Tous les dossiers de cores candidats (existants), par ordre de priorité.

    Couvre Flatpak, paquets système (dnf/apt/pacman…), snap, AppImage,
    dossiers utilisateur et le dossier déclaré dans retroarch.cfg.
    """
    home = Path.home()
    dirs: list[Path] = []
    if retroarch_path and is_flatpak(retroarch_path):
        dirs.append(flatpak_cores_dir())
    if retroarch_path and not is_flatpak(retroarch_path):
        exe = Path(retroarch_path).expanduser()
        # À côté de l'exécutable : standard portable (Windows inclus)
        if exe.is_file():
            dirs.append(exe.parent / "cores")
    # Dossier déclaré par RetroArch lui-même (le plus fiable)
    cfg_dir = cfg_libretro_directory()
    if cfg_dir:
        dirs.append(cfg_dir)
    if sys.platform == "win32":
        for key in ("APPDATA", "LOCALAPPDATA"):
            val = os.environ.get(key)
            if val:
                dirs.append(Path(val) / "RetroArch" / "cores")
    elif sys.platform == "darwin":
        dirs += [
            Path("/Applications/RetroArch.app/Contents/Resources/cores"),
            home / "Library/Application Support/RetroArch/cores",
        ]
    else:
        dirs += [
            home / ".config/retroarch/cores",  # Linux standard (dnf, apt, pacman…)
            home / ".retroarch/cores",
            home / "snap/retroarch/current/.config/retroarch/cores",
            Path("/snap/retroarch/current/usr/lib/libretro"),
            Path("/usr/lib/libretro"),  # Arch, Fedora
            Path("/usr/lib64/libretro"),  # Fedora x86_64
            Path("/usr/lib/x86_64-linux-gnu/libretro"),  # Debian / Ubuntu
            Path("/usr/lib/i386-linux-gnu/libretro"),
            Path("/usr/lib/aarch64-linux-gnu/libretro"),
            Path("/usr/lib/arm-linux-gnueabihf/libretro"),
            Path("/usr/share/libretro/cores"),
        ]
        # Flatpak en secours même si un autre RetroArch est détecté
        dirs.append(flatpak_cores_dir())
    out: list[Path] = []
    for d in dirs:
        if d not in out and d.is_dir():
            out.append(d)
    return out


def default_cores_dir(retroarch_path: str | None) -> str | None:
    dirs = cores_dirs(retroarch_path)
    return str(dirs[0]) if dirs else None


def core_extension() -> str:
    if sys.platform == "win32":
        return ".dll"
    if sys.platform == "darwin":
        return ".dylib"
    return ".so"


def resolve_core_path(cores_dir: str | None, system_id: str) -> str | None:
    """Cherche le core du système dans le dossier principal puis dans tous les autres.

    Priorité : ordre de préférence de RETROARCH_CORES (ex. melondsds avant desmume),
    puis correspondance approximative (ex. melondsds_libretro.so pour « melonds »).
    """
    names = RETROARCH_CORES.get(system_id)
    if not names:
        return None
    search: list[Path] = []
    if cores_dir:
        p = Path(cores_dir).expanduser()
        if p.is_dir():
            search.append(p)
    for d in cores_dirs(None):
        if d not in search:
            search.append(d)
    if not search:
        return None
    ext = core_extension()
    # 1) Noms exacts, par ordre de préférence
    for name in names:
        for base in search:
            for candidate in (base / f"{name}{ext}", base / f"{name}.so", base / f"{name}.dll"):
                if candidate.is_file():
                    return str(candidate)
    # 2) Correspondance approximative
    for name in names:
        stem = name.replace("_libretro", "").lower()
        for base in search:
            try:
                files = sorted(f for f in base.iterdir() if f.is_file())
            except OSError:
                continue
            for f in files:
                fname = f.name.lower()
                if stem in fname and "libretro" in fname:
                    return str(f)
    return None


def find_native(system_id: str) -> str | None:
    for name in NATIVE_HINTS.get(system_id, []):
        w = which(name)
        if w:
            return w
    return None


# Émulateurs natifs installés en Flatpak (Linux) : app id → nom lisible.
FLATPAK_NATIVE: dict[str, tuple[str, str]] = {
    "nds": ("net.kuribo64.melonDS", "melonDS (Flatpak)"),
    "wii": ("org.DolphinEmu.dolphin-emu", "Dolphin (Flatpak)"),
    "gamecube": ("org.DolphinEmu.dolphin-emu", "Dolphin (Flatpak)"),
    "gba": ("io.mgba.mGBA", "mGBA (Flatpak)"),
    "gb": ("io.mgba.mGBA", "mGBA (Flatpak)"),
    "psx": ("org.duckstation.DuckStation", "DuckStation (Flatpak)"),
    "ps2": ("net.pcsx2.PCSX2", "PCSX2 (Flatpak)"),
    "psp": ("org.ppsspp.PPSSPP", "PPSSPP (Flatpak)"),
    "dreamcast": ("org.flycast.Flycast", "Flycast (Flatpak)"),
    "snes": ("com.snes9x.Snes9x", "Snes9x (Flatpak)"),
}


def _flatpak_app_installed(app_id: str) -> bool:
    if sys.platform in ("win32", "darwin"):
        return False
    return (Path.home() / ".var/app" / app_id).is_dir() or (
        Path("/var/lib/flatpak/app") / app_id
    ).is_dir()


def flatpak_native(system_id: str) -> tuple[str, str] | None:
    """Émulateur natif installé en Flatpak : (app id, nom lisible)."""
    entry = FLATPAK_NATIVE.get(system_id)
    if not entry:
        return None
    app_id, label = entry
    return (app_id, label) if _flatpak_app_installed(app_id) else None


def autofill(config: dict) -> dict:
    """Complète path RetroArch / cores / natifs si vides."""
    # Dossier ROMs par défaut : rien à configurer, les jeux manquants se
    # téléchargent depuis le site au premier lancement.
    if not (config.get("roms_dir") or "").strip():
        config["roms_dir"] = str(Path.home() / "KirbyRetroROMs")
    ra = config.setdefault("retroarch", {})
    if not ra.get("path"):
        found = find_retroarch()
        if found:
            ra["path"] = found
    if not ra.get("cores_dir"):
        cores = default_cores_dir(ra.get("path"))
        if cores:
            ra["cores_dir"] = cores
    emus = config.setdefault("emulators", {})
    for system_id in NATIVE_HINTS:
        entry = emus.setdefault(system_id, {})
        if not entry.get("path"):
            native = find_native(system_id)
            if native:
                entry["path"] = native
                entry.setdefault("args", ["{rom}"])
    return config
