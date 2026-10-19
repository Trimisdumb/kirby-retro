"""Diagnostic du launcher : « ./run.sh doctor » / « run.bat doctor »."""
from __future__ import annotations

import sys
from pathlib import Path

from . import __version__
from .api import fetch_library
from .config import config_path, load_config
from .cores import RETROARCH_CORES
from .detect import autofill, cores_dirs, resolve_core_path, retroarch_executable_ok
from .netplay import candidate_addresses
from .protocol import status as protocol_status
from . import wiimote

CHECK_SYSTEMS = (
    "nes", "snes", "gb", "gba", "nds", "n64", "psx", "ps2", "psp",
    "segaMD", "sega32x", "segaSaturn", "dreamcast", "gamecube", "wii",
    "3ds", "arcade",
)


def _ok(flag: bool) -> str:
    return "[OK]" if flag else "[!!]"


def collect() -> str:
    lines: list[str] = []
    lines.append(f"Kirby Retro Launcher v{__version__} — diagnostic")
    lines.append(f"Plateforme : {sys.platform} · Python {sys.version.split()[0]}")
    try:
        import tkinter  # noqa: F401

        tkinter_ok = True
    except Exception:  # noqa: BLE001
        tkinter_ok = False
    lines.append(
        "Interface  : tkinter " + _ok(tkinter_ok)
        + ("" if tkinter_ok else " — Fedora : sudo dnf install python3-tkinter · Debian/Ubuntu : sudo apt install python3-tk")
    )
    lines.append("")

    cfg_file = config_path()
    lines.append(f"Config     : {cfg_file}")
    lines.append(f"             {'trouvée' if cfg_file.is_file() else 'absente (valeurs par défaut)'}")

    config = autofill(load_config())

    site = (config.get("site_url") or "").strip().rstrip("/") or "https://retro.kirbytrim.buzz"
    try:
        library = fetch_library(site, timeout=10)
        counts = [s for s in (library.get("systems") or []) if s.get("count")]
        lines.append(
            f"Site       : {site} [OK] — {library.get('totalGames', 0)} jeu(x), "
            f"{len(counts)} console(s) avec jeux"
        )
    except Exception as exc:  # noqa: BLE001
        lines.append(f"Site       : {site} [!!] — {exc}")

    roms = (config.get("roms_dir") or "").strip()
    roms_path = Path(roms).expanduser() if roms else None
    roms_exists = bool(roms_path and roms_path.is_dir())
    lines.append(
        f"ROMs       : {roms or '(non défini)'} "
        f"[{'OK — présent' if roms_exists else 'sera créé au premier téléchargement'}]"
    )

    ra = config.get("retroarch") or {}
    ra_path = (ra.get("path") or "").strip()
    ra_ok = retroarch_executable_ok(ra_path)
    lines.append(f"RetroArch  : {ra_path or '(non trouvé)'} {_ok(ra_ok)}")

    cores_dir = (ra.get("cores_dir") or "").strip()
    cores_ok = bool(cores_dir) and Path(cores_dir).is_dir()
    core_count = 0
    if cores_ok:
        core_count = len([f for f in Path(cores_dir).iterdir() if "libretro" in f.name])
    lines.append(f"Cores      : {cores_dir or '(non trouvé)'} {_ok(cores_ok)} — {core_count} fichier(s)")
    extras = [str(d) for d in cores_dirs(ra_path) if str(d) != cores_dir]
    if extras:
        lines.append(f"             autres dossiers explorés : {' · '.join(extras)}")
    if cores_ok:
        for system_id in CHECK_SYSTEMS:
            core = resolve_core_path(cores_dir, system_id)
            alts = RETROARCH_CORES.get(system_id) or ("?",)
            detail = Path(core).name if core else "à installer : " + " / ".join(alts)
            lines.append(f"             · {system_id:<10} {_ok(bool(core))} {detail}")

    emulators = config.get("emulators") or {}
    natives = [f"{sid} → {entry.get('path')}" for sid, entry in emulators.items() if entry.get("path")]
    lines.append("Natif      : " + (" | ".join(natives) if natives else "aucun émulateur standalone détecté"))

    addresses = candidate_addresses()
    if not ra_ok:
        lines.append("Netplay    : [!!] nécessite RetroArch (voir ci-dessus)")
    elif addresses:
        listing = " · ".join(f"{tag} {ip}" for tag, ip in addresses)
        lines.append(f"Netplay    : [OK] — adresses pour héberger : {listing} (port 55435)")
    else:
        lines.append("Netplay    : [OK] — aucune adresse détectée (Tailscale/réseau) ; le port UDP 55435 reste utilisable")

    state = wiimote.status()
    bar = "Dolphin Bar détecté" if state["bar"] else "Dolphin Bar non détecté"
    if state["access"] is True:
        access = "accès OK"
    elif state["access"] is False:
        access = "accès refusé (règle udev à installer)"
    else:
        access = "accès non vérifiable (Wiimote éteinte ?)"
    conf = "configuré" if state["configured"] else "à configurer (Paramètres → Manette Wii…)"
    lines.append(f"Wiimote    : {bar} — {access} — RetroArch {conf}")

    lines.append(f"Protocole  : {protocol_status()}")
    return "\n".join(lines)
