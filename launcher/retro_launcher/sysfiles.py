"""Fichiers système manquants des cores RetroArch (ex. Dolphin).

RetroArch les installe via « Mise à jour en ligne → Fichiers système des
cores » ; ce module fait pareil : téléchargement depuis le buildbot officiel
puis extraction dans le dossier « system » de RetroArch. Ça évite le
bandeau « Core file codehandler.bin missing! » à chaque lancement Wii.
"""
from __future__ import annotations

import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

from .config import ensure_ca_bundle
from .detect import cfg_value, resolve_cfg_path, retroarch_cfg

USER_AGENT = "KirbyRetroLauncher/1.0"

# Asset officiel utilisé par « Core System Files Downloader » de RetroArch.
DOLPHIN_ASSET_URL = "https://buildbot.libretro.com/assets/system/Dolphin.zip"

# Fichiers présents dans Dolphin.zip qui suffisent pour les jeux Wii/GC.
_DOLPHIN_NEEDED = ("dolphin-emu/Sys/codehandler.bin",)


def retroarch_system_dir(cfg_candidates: list[Path] | None = None) -> Path | None:
    """Dossier « system » de RetroArch (retroarch.cfg → system_directory)."""
    cfg, text = retroarch_cfg(cfg_candidates)
    if cfg is not None:
        resolved = resolve_cfg_path(cfg_value(text, "system_directory") or "default", cfg.parent)
        return resolved if resolved is not None else cfg.parent / "system"
    if cfg_candidates is not None:
        return None
    home = Path.home()
    for candidate in (
        home / ".config/retroarch/system",
        home / ".var/app/org.libretro.RetroArch/config/retroarch/system",
        home / ".retroarch/system",
        home / "snap/retroarch/current/.config/retroarch/system",
    ):
        if candidate.parent.is_dir():
            return candidate
    return None


def dolphin_sysfiles_ok(system_dir: Path | None) -> bool:
    """Vrai si RetroArch a déjà les fichiers dont le core Dolphin a besoin."""
    if system_dir is None:
        return False
    return all((system_dir / rel).is_file() for rel in _DOLPHIN_NEEDED)


def ensure_dolphin_sysfiles(
    progress: callable | None = None,
    cfg_candidates: list[Path] | None = None,
) -> str | None:
    """Installe les fichiers système du core Dolphin s'il en manque.

    Renvoie un message si quelque chose a été installé (ou en cas d'échec) ;
    None quand il n'y a rien à faire. Ne lève jamais : le lancement continue.
    """
    system_dir = retroarch_system_dir(cfg_candidates)
    if system_dir is None or dolphin_sysfiles_ok(system_dir):
        return None
    if progress:
        progress("Fichiers système Dolphin manquants — téléchargement…")
    ensure_ca_bundle()
    try:
        request = urllib.request.Request(DOLPHIN_ASSET_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120.0) as response:
            archive = io.BytesIO(response.read())
        _extract_zip(archive, system_dir)
    except Exception as exc:  # noqa: BLE001 — on ne bloque pas le lancement
        return (
            f"Fichiers système Dolphin : téléchargement impossible ({exc}). Tu peux les "
            "installer dans RetroArch → Mise à jour en ligne → Fichiers système des cores."
        )
    return "Fichiers système Dolphin installés pour RetroArch"


def _extract_zip(archive: io.BytesIO, dest: Path) -> None:
    """Extrait une archive en refusant les chemins hors du dossier cible."""
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            name = Path(info.filename)
            if info.is_dir() or name.is_absolute() or ".." in name.parts:
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink)
