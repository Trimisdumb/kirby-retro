"""Manette Wii (Wiimote) avec Dolphin Bar Mayflash, mode 4 — via le core Dolphin.

RetroArch n'active rien tout seul pour une Wiimote : on applique, avant un
lancement Wii, les trois réglages qui reproduisent le Dolphin natif :

  · « Wiimote Continuous Scanning » — le core cherche la Wiimote en continu ;
  · « Wiimote IR Passthrough » — le pointeur de la sensor bar arrive au jeu ;
  · port 1 en « Real WiiMote » — la vraie manette pilote le joueur 1.

Tout est écrit dans la configuration propre au core Dolphin de RetroArch
(dossier config/dolphin-emu), jamais dans le retroarch.cfg général.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from .config import subprocess_env
from .detect import retroarch_cfg

CORE_NAME = "dolphin-emu"  # nom du dossier/config du core dans RetroArch
REAL_WIIMOTE_DEVICE = "1536"  # RETRO_DEVICE_REAL_WIIMOTE du core, (6 << 8) | 0
OPT_KEYS = {
    "dolphin_wiimote_continuous_scanning": "enabled",
    "dolphin_ir_passthrough": "enabled",
}
PORT_KEY = "input_libretro_device_p1"

# Dolphin Bar (Mayflash) en mode 4 : le dongle se présente comme 057e:0306.
DOLPHIN_BAR_IDS = (("057e", "0306"),)
UDEV_RULE_PATH = Path("/etc/udev/rules.d/69-dolphin.rules")
UDEV_RULE = (
    'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="057e", ATTRS{idProduct}=="0306", MODE="0666"'
)


def retroarch_config_dir() -> Path | None:
    """Dossier de configuration de RetroArch (celui du retroarch.cfg détecté)."""
    cfg, _ = retroarch_cfg()
    return cfg.parent if cfg else None


def _core_dir(base: Path) -> Path:
    return base / "config" / CORE_NAME


def _read_ini_value(path: Path, key: str) -> str | None:
    """Valeur de « clé = "valeur" » dans un fichier ini, sinon None."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        head, sep, value = line.partition("=")
        if sep and head.strip() == key:
            return value.strip().strip('"')
    return None


def _set_ini(path: Path, updates: dict[str, str], remove: tuple[str, ...] = ()) -> bool:
    """Met à jour des clés en gardant le reste du fichier intact.

    `updates` remplace (ou ajoute) des clés, `remove` supprime des lignes —
    sert à rendre le port 1 à une manette classique pour les jeux GameCube.
    """
    lines: list[str] = []
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return False
    done: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key is not None and key in updates:
            out.append(f'{key} = "{updates[key]}"')
            done.add(key)
        elif key is not None and key in remove:
            continue
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in done:
            out.append(f'{key} = "{value}"')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def enabled(base: Path | None = None) -> bool:
    """Les trois réglages Wiimote sont-ils déjà en place ?"""
    base = base or retroarch_config_dir()
    if base is None:
        return False
    core = _core_dir(base)
    for key, value in OPT_KEYS.items():
        if _read_ini_value(core / f"{CORE_NAME}.opt", key) != value:
            return False
    return _read_ini_value(core / f"{CORE_NAME}.cfg", PORT_KEY) == REAL_WIIMOTE_DEVICE


def apply(base: Path | None = None) -> str | None:
    """Applique les réglages Wiimote pour un lancement Wii.

    Renvoie une note à afficher si quelque chose a changé, sinon None.
    """
    base = base or retroarch_config_dir()
    if base is None or enabled(base):
        return None
    core = _core_dir(base)
    ok = _set_ini(core / f"{CORE_NAME}.opt", dict(OPT_KEYS))
    ok = _set_ini(core / f"{CORE_NAME}.cfg", {PORT_KEY: REAL_WIIMOTE_DEVICE}) and ok
    if not ok:
        return None
    return "Manette Wii : RetroArch configuré (Wiimote réelle + pointeur)"


def release_controller_port(base: Path | None = None) -> None:
    """Lancement GameCube : rend le port 1 à une manette classique."""
    base = base or retroarch_config_dir()
    if base is None:
        return
    cfg = _core_dir(base) / f"{CORE_NAME}.cfg"
    if _read_ini_value(cfg, PORT_KEY) == REAL_WIIMOTE_DEVICE:
        _set_ini(cfg, {}, remove=(PORT_KEY,))


def on_launch(
    config: dict[str, Any], system: str, core: str, progress: Callable[[str], None] | None = None
) -> None:
    """Appelé juste avant un lancement Wii/GameCube dans RetroArch."""
    if "dolphin" not in Path(core).stem.lower():
        return
    if not config.get("configure_wiimote"):
        return
    try:
        if system == "wii":
            note = apply()
        else:
            release_controller_port()
            return
    except OSError:
        return
    if note and progress:
        progress(note)


# ―― Dolphin Bar : détection et accès hidraw (pour le diagnostic) ――


def dolphin_bar_connected() -> bool:
    """Le Dolphin Bar est-il branché en USB ?"""
    for dev in Path("/sys/bus/usb/devices").glob("*"):
        try:
            vendor = (dev / "idVendor").read_text(encoding="utf-8").strip().lower()
            product = (dev / "idProduct").read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if (vendor, product) in DOLPHIN_BAR_IDS:
            return True
    return False


def dolphin_bar_devices() -> list[Path]:
    """Nœuds /dev/hidraw* du Dolphin Bar (057e:0306)."""
    nodes: list[Path] = []
    for entry in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        try:
            uevent = (entry / "device" / "uevent").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "0000057E:00000306" in uevent.upper():
            nodes.append(Path("/dev") / entry.name)
    return nodes


def access_ok() -> bool | None:
    """Accès en lecture/écriture au Dolphin Bar : True/False, None si inconnu."""
    nodes = dolphin_bar_devices()
    if not nodes:
        return None
    return all(os.access(node, os.R_OK | os.W_OK) for node in nodes)


def install_udev_rule() -> str:
    """Installe la règle udev du Dolphin Bar (mot de passe administrateur demandé)."""
    script = (
        f"printf '%s\\n' '{UDEV_RULE}' > {UDEV_RULE_PATH}\n"
        "udevadm control --reload-rules\n"
        "udevadm trigger --subsystem-match=hidraw\n"
    )
    try:
        result = subprocess.run(
            ["pkexec", "sh", "-c", script],
            env=subprocess_env(),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("pkexec introuvable — voir la règle à créer à la main") from exc
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or result.stdout).strip() or "installation refusée"
        )
    return "Règle installée : le Dolphin Bar est maintenant accessible."


def status() -> dict[str, Any]:
    """État du support Wiimote pour l'interface."""
    base = retroarch_config_dir()
    return {
        "bar": dolphin_bar_connected(),
        "access": access_ok(),
        "configured": enabled(base) if base else False,
        "ra_dir": str(base) if base else "",
    }
