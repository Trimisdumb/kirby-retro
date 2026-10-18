"""Résolution du chemin ROM + lancement émulateur."""
from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .api import download_rom
from .config import subprocess_env
from .cores import RETROARCH_CORES
from .detect import cores_dirs, is_flatpak, resolve_core_path, retroarch_executable_ok
from .netplay import DEFAULT_PORT as NETPLAY_DEFAULT_PORT, write_appendconfig
from .saves import auto_sync_before_launch


class LaunchError(Exception):
    pass


def local_rom_path(roms_dir: str, system: str, file: str) -> Path:
    return Path(roms_dir).expanduser().resolve() / system / file


def ensure_rom(
    config: dict[str, Any],
    system: str,
    file: str,
    *,
    progress: callable | None = None,
) -> Path:
    roms_dir = (config.get("roms_dir") or "").strip()
    if not roms_dir:
        raise LaunchError(
            "Aucun dossier ROMs configuré.\n"
            "Ouvre Paramètres et indique le dossier qui contient nes/, nds/, n64/, etc."
        )
    path = local_rom_path(roms_dir, system, file)
    if path.is_file():
        return path

    if not config.get("download_missing_roms", True):
        raise LaunchError(f"ROM introuvable localement :\n{path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    site = (config.get("site_url") or "https://retro.kirbytrim.buzz").rstrip("/")
    if progress:
        progress(f"Téléchargement de {file}…")
    try:
        download_rom(site, system, file, str(path))
    except Exception as exc:  # noqa: BLE001
        if path.exists():
            path.unlink(missing_ok=True)
        raise LaunchError(f"Échec du téléchargement depuis {site} :\n{exc}") from exc
    if not path.is_file() or path.stat().st_size == 0:
        raise LaunchError("Fichier ROM vide ou manquant après téléchargement.")
    return path


def _run(cmd: list[str], cwd: str | None = None) -> None:
    if not cmd or not cmd[0]:
        raise LaunchError("Commande d'émulateur vide.")
    try:
        env = subprocess_env()
        if sys.platform == "win32":
            subprocess.Popen(cmd, cwd=cwd, close_fds=True, env=env)
        else:
            subprocess.Popen(cmd, cwd=cwd, close_fds=True, start_new_session=True, env=env)
    except OSError as exc:
        raise LaunchError(f"Impossible de lancer :\n{' '.join(cmd)}\n{exc}") from exc


def launch_native(
    config: dict[str, Any],
    system: str,
    rom: Path,
    *,
    progress: callable | None = None,
) -> bool:
    """Tente un émulateur standalone. Retourne True si lancé."""
    entry = (config.get("emulators") or {}).get(system) or {}
    path = (entry.get("path") or "").strip()
    if not path or not Path(path).exists():
        return False
    note = auto_sync_before_launch(config, system, rom.name, rom_path=rom, to_retroarch=False)
    if note and progress:
        progress(note)
    args = entry.get("args") or ["{rom}"]
    cmd = [path]
    for a in args:
        cmd.append(str(a).replace("{rom}", str(rom)).replace("{rom_dir}", str(rom.parent)))
    _run(cmd)
    return True


def retroarch_command(ra_path: str) -> list[str]:
    """Commande de base pour lancer RetroArch (gère l'installation Flatpak)."""
    value = ra_path.strip()
    if is_flatpak(value):
        return shlex.split(value)
    return [value]


def _resolve_core(ra: dict[str, Any], system: str) -> str:
    """Chemin du core pour ce système, sinon erreur explicite et utile."""
    core = resolve_core_path(ra.get("cores_dir"), system)
    if core:
        return core
    names = " / ".join(RETROARCH_CORES.get(system, ("?",)))
    searched = cores_dirs(ra.get("path"))
    listing = "\n".join(f"  · {d}" for d in searched) if searched else "  (aucun dossier de cores trouvé)"
    raise LaunchError(
        f"Core RetroArch introuvable pour « {system} ».\n"
        f"Core attendu : {names}\n"
        f"Dossiers consultés :\n{listing}\n\n"
        "Ouvre RetroArch → « Mise à jour en ligne » → « Gestionnaire de cœurs », "
        "installe-le puis relance."
    )


def launch_retroarch(
    config: dict[str, Any],
    system: str,
    rom: Path,
    *,
    progress: callable | None = None,
) -> bool:
    ra = config.get("retroarch") or {}
    ra_path = (ra.get("path") or "").strip()
    if not retroarch_executable_ok(ra_path):
        return False
    core = _resolve_core(ra, system)
    note = auto_sync_before_launch(config, system, rom.name, rom_path=rom, to_retroarch=True)
    if note and progress:
        progress(note)
    cmd = retroarch_command(ra_path) + ["-L", core, str(rom)]
    cwd = None if is_flatpak(ra_path) else str(Path(ra_path).parent)
    _run(cmd, cwd=cwd)
    return True


def launch_netplay(
    config: dict[str, Any],
    system: str,
    file: str,
    *,
    host: bool,
    address: str = "",
    port: int = NETPLAY_DEFAULT_PORT,
    nickname: str = "",
    password: str = "",
    use_relay: bool = False,
    progress: callable | None = None,
) -> str:
    """Partie en ligne (netplay RetroArch). RetroArch est obligatoire."""
    if progress:
        progress("Préparation de la ROM…")
    rom = ensure_rom(config, system, file, progress=progress)

    ra = config.get("retroarch") or {}
    ra_path = (ra.get("path") or "").strip()
    if not retroarch_executable_ok(ra_path):
        raise LaunchError(
            "Le jeu en ligne utilise le netplay de RetroArch.\n"
            "Installe RetroArch (Paramètres → Diagnostic pour vérifier), puis réessaie."
        )
    core = _resolve_core(ra, system)
    note = auto_sync_before_launch(config, system, file, rom_path=rom, to_retroarch=True)
    if note and progress:
        progress(note)

    try:
        port = int(port)
    except (TypeError, ValueError):
        raise LaunchError(f"Port netplay invalide : {port!r}") from None
    if not 1 <= port <= 65535:
        raise LaunchError(f"Port netplay invalide : {port} (attendu : 1 – 65535).")

    nickname = (nickname or "").strip() or "Kirby"
    args: list[str] = []
    if host:
        args.append("--host")
        label = f"hôte « {nickname} »"
    else:
        address = (address or "").strip()
        if not address:
            raise LaunchError("Indique l'adresse de la partie à rejoindre (donnée par l'hôte).")
        args.append(f"--connect={address}")
        label = f"rejoint {address}"
    args += [f"--port={port}", f"--nick={nickname}"]
    cfg_file = write_appendconfig(nickname=nickname, port=port, password=password, use_relay=use_relay)
    args.append(f"--appendconfig={cfg_file}")

    cmd = retroarch_command(ra_path) + args + ["-L", core, str(rom)]
    cwd = None if is_flatpak(ra_path) else str(Path(ra_path).parent)
    _run(cmd, cwd=cwd)
    return f"netplay ({label}) · {rom.name}"


def launch_game(
    config: dict[str, Any],
    system: str,
    file: str,
    *,
    progress: callable | None = None,
) -> str:
    """
    Lance le jeu. Stratégie :
    1. Si system dans prefer_native_for → natif puis RetroArch
    2. Sinon RetroArch puis natif
    """
    if progress:
        progress("Préparation de la ROM…")
    rom = ensure_rom(config, system, file, progress=progress)
    prefer_native = system in set(config.get("prefer_native_for") or [])

    errors: list[str] = []

    def try_native() -> bool:
        try:
            if launch_native(config, system, rom, progress=progress):
                return True
        except LaunchError as exc:
            errors.append(str(exc))
        return False

    def try_ra() -> bool:
        try:
            if launch_retroarch(config, system, rom, progress=progress):
                return True
        except LaunchError as exc:
            errors.append(str(exc))
        return False

    if prefer_native:
        if try_native():
            return f"Natif · {rom.name}"
        if try_ra():
            return f"RetroArch · {rom.name}"
    else:
        if try_ra():
            return f"RetroArch · {rom.name}"
        if try_native():
            return f"Natif · {rom.name}"

    detail = "\n".join(errors) if errors else "Aucun émulateur configuré."
    raise LaunchError(
        f"Impossible de lancer {system}/{file}.\n\n{detail}\n\n"
        "Installe RetroArch (recommandé) ou un émulateur natif, puis relance. "
        "Diagnostic complet : « ./run.sh doctor » (Linux) ou « run.bat doctor » (Windows)."
    )
