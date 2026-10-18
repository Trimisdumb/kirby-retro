"""Trouver et copier les sauvegardes de jeu entre émulateurs et RetroArch.

RetroArch lit un fichier .srm par jeu, nommé comme la ROM. Les émulateurs
natifs écrivent d'autres formats (melonDS en .sav, DeSmuME en .dsv, N64 en
.eep/.sra/.fla/.mpk...) : on convertit ici au moment de la copie.

Avant d'écraser une sauvegarde existante, elle est recopiée en .bak-<date>.
"""
from __future__ import annotations

import datetime as _dt
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .detect import retroarch_cfg_candidates

# Tailles possibles d'une sauvegarde DS (128 Ko à 2 Mo, et les petites cartes
# de jeux GBA/GB). Sert à reconnaître un .dsv brut derrière son en-tête.
DS_SIZES = {
    8 * 1024,
    32 * 1024,
    64 * 1024,
    128 * 1024,
    256 * 1024,
    512 * 1024,
    1024 * 1024,
    2 * 1024 * 1024,
}

# Le .srm de mupen64plus-next (RetroArch, N64) concatène tout dans un seul
# fichier : eeprom, 4 mempaks, sram, flashram. Tailles et décalages en octets.
N64_LAYOUT: dict[str, tuple[int, int]] = {
    "n64-eep": (0x00000, 0x800),  # 2048
    "n64-mpk": (0x00800, 0x20000),  # 4 x 32768
    "n64-sra": (0x20800, 0x8000),  # 32768
    "n64-fla": (0x28800, 0x20000),  # 131072
}
N64_TOTAL = 0x48800  # 296960

_KIND_BY_EXT = {
    ".sav": "raw",
    ".srm": "raw",
    ".mcd": "raw",
    ".mcr": "raw",
    ".gci": "raw",
    ".raw": "raw",
    ".dsv": "dsv",
    ".eep": "n64-eep",
    ".sra": "n64-sra",
    ".fla": "n64-fla",
    ".mpk": "n64-mpk",
}

RETROARCH_EXT = "srm"


class SaveError(Exception):
    """Erreur à afficher telle quelle dans l'interface."""


@dataclass
class SaveFile:
    path: Path
    source: str
    kind: str
    system: str

    @classmethod
    def from_path(cls, path: Path, system: str, source: str = "fichier choisi") -> "SaveFile":
        path = Path(path).expanduser()
        return cls(path, source, _KIND_BY_EXT.get(path.suffix.lower(), "raw"), system)

    def size_ko(self) -> int:
        try:
            return max(1, self.path.stat().st_size // 1024)
        except OSError:
            return 0

    def date(self) -> str:
        try:
            stamp = _dt.datetime.fromtimestamp(self.path.stat().st_mtime)
            return stamp.strftime("%d/%m/%Y %H:%M")
        except OSError:
            return "?"

    def mtime(self) -> float:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return 0.0


# dossier de sauvegardes de RetroArch

def _resolve_retroarch_path(value: str, base: Path) -> Path | None:
    """Interprète une valeur de retroarch.cfg ("default", ":/chemin", "~/...")."""
    value = value.strip()
    if not value or value in ("default", ":", ":/"):
        return None
    if value.startswith(":"):
        value = value[1:]
    if value.startswith("~"):
        return Path(value).expanduser()
    path = Path(value)
    return path if path.is_absolute() else base / path


def retroarch_save_dir(cfg_candidates: list[Path] | None = None) -> tuple[Path | None, str]:
    """Dossier des sauvegardes de RetroArch, avec une explication lisible."""
    for cfg in cfg_candidates if cfg_candidates is not None else retroarch_cfg_candidates():
        if not cfg.is_file():
            continue
        value: str | None = None
        try:
            for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("savefile_directory"):
                    _, _, value = line.partition("=")
                    value = value.strip().strip('"').strip("'")
                    break
        except OSError:
            continue
        resolved = _resolve_retroarch_path(value or "default", cfg.parent)
        if resolved is not None:
            return resolved, f"retroarch.cfg ({cfg}) → savefile_directory"
        return cfg.parent / "saves", f"retroarch.cfg ({cfg}) → dossier « saves »"
    if cfg_candidates is not None:
        return None, "aucun retroarch.cfg trouvé"
    home = Path.home()
    for candidate in (
        home / ".config/retroarch/saves",
        home / ".var/app/org.libretro.RetroArch/config/retroarch/saves",
        home / ".retroarch/saves",
        home / "snap/retroarch/current/.config/retroarch/saves",
    ):
        if candidate.parent.is_dir():
            return candidate, f"emplacement classique ({candidate.parent})"
    return None, "RetroArch introuvable — règle-le dans Paramètres, ou exporte une copie"


# emplacements des émulateurs natifs

def _candidate_dirs(
    system: str,
    roms_dir: str | None,
    cfg_candidates: list[Path] | None = None,
) -> list[tuple[str, Path, tuple[str, ...]]]:
    """(nom de l'émulateur, dossier, extensions) à fouiller pour ce système."""
    home = Path.home()
    out: list[tuple[str, Path, tuple[str, ...]]] = []

    def add(label: str, path: Path | None, exts: tuple[str, ...]) -> None:
        if path is not None:
            out.append((label, path, exts))

    rom_sys: Path | None = None
    if roms_dir:
        rom_sys = Path(roms_dir).expanduser() / system

    if system == "nds":
        add("melonDS", rom_sys, (".sav",))
        add("melonDS (dossier saves)", home / ".local/share/melonDS/saves", (".sav",))
        add("melonDS (bureau)", home / "melonDS/saves", (".sav",))
        add("DeSmuME", rom_sys, (".dsv",))
        add("DeSmuME (config)", home / ".config/desmume", (".dsv",))
        add("DeSmuME (dossier)", home / ".desmume", (".dsv",))
    elif system == "n64":
        add("simple64", home / ".local/share/simple64/save", (".eep", ".sra", ".fla", ".mpk"))
        add("mupen64plus", home / ".local/share/mupen64plus", (".eep", ".sra", ".fla", ".mpk"))
        add("Project64 (dossier ROMs)", rom_sys, (".eep", ".sra", ".fla", ".mpk"))
        add("mupen64plus (à côté de la ROM)", rom_sys, (".srm",))
    elif system == "psx":
        add("DuckStation", home / ".local/share/duckstation/memcards", (".mcd", ".mcr"))
        add("DuckStation (portable)", rom_sys, (".mcd", ".mcr"))
        add("PCSX2", home / ".config/PCSX2/memcards", (".mcr", ".mcd"))
    elif system in ("gba", "gbc", "gb"):
        add("mGBA (à côté de la ROM)", rom_sys, (".sav",))
        add("mGBA (dossier saves)", home / ".local/share/mgba/saves", (".sav",))
        add("VisualBoyAdvance", home / ".config/vba", (".sav",))
    else:
        add("émulateur (à côté de la ROM)", rom_sys, (".sav", ".srm"))

    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        if system == "nds":
            add("melonDS (AppData)", appdata / "melonDS" / "saves", (".sav",))
        if system == "n64":
            add("simple64 (AppData)", appdata / "simple64" / "save", (".eep", ".sra", ".fla", ".mpk"))

    ra_dir, _why = retroarch_save_dir(cfg_candidates)
    if ra_dir is not None:
        add("RetroArch", ra_dir, (".srm",))

    add(
        "à côté de la ROM",
        rom_sys,
        (".sav", ".srm", ".dsv", ".eep", ".sra", ".fla", ".mpk", ".mcd", ".mcr"),
    )
    return out


def find_saves(
    system: str,
    file: str,
    roms_dir: str | None = None,
    cfg_candidates: list[Path] | None = None,
) -> list[SaveFile]:
    """Sauvegardes trouvées pour ce jeu, les plus récentes d'abord."""
    stem = Path(file).stem
    found: list[SaveFile] = []
    seen: set[Path] = set()
    for label, folder, exts in _candidate_dirs(system, roms_dir, cfg_candidates):
        try:
            if not folder.is_dir():
                continue
        except OSError:
            continue
        for ext in exts:
            candidate = folder / (stem + ext)
            try:
                if candidate.is_file() and candidate not in seen:
                    seen.add(candidate)
                    found.append(SaveFile(candidate, label, _KIND_BY_EXT.get(ext, "raw"), system))
            except OSError:
                continue
    found.sort(key=lambda save: save.mtime(), reverse=True)
    return found


# conversions

def _strip_dsv(data: bytes) -> tuple[bytes | None, str]:
    """Retire l'en-tête et le pied DeSmuME pour retrouver la sauvegarde brute."""
    if len(data) in DS_SIZES:
        return data, "déjà brute"
    for head, tail in ((122, 122), (122, 0), (0, 122), (512, 0), (0, 512), (256, 0)):
        inner = len(data) - head - tail
        if inner in DS_SIZES:
            stop = len(data) - tail if tail else len(data)
            return data[head:stop], f"en-tête/pied DeSmuME retirés ({head}+{tail} octets)"
    return None, "format .dsv non reconnu (taille inattendue)"


def to_retroarch_bytes(sources: list[SaveFile]) -> tuple[bytes | None, str]:
    """Contenu du .srm RetroArch à écrire, à partir des fichiers sélectionnés."""
    if not sources:
        return None, "aucune sauvegarde sélectionnée"
    n64 = [save for save in sources if save.kind.startswith("n64-")]
    if n64:
        buf = bytearray(N64_TOTAL)
        fla_offset, fla_size = N64_LAYOUT["n64-fla"]
        buf[fla_offset : fla_offset + fla_size] = b"\xff" * fla_size
        notes: list[str] = []
        for save in n64:
            offset, size = N64_LAYOUT[save.kind]
            data = save.path.read_bytes()
            if len(data) > size:
                data = data[:size]
            buf[offset : offset + len(data)] = data
            notes.append(f"{save.kind[4:]} → 0x{offset:05x}")
        return bytes(buf), "fusion N64 (" + ", ".join(notes) + ")"
    save = sources[0]
    data = save.path.read_bytes()
    if save.kind == "dsv":
        return _strip_dsv(data)
    note = "copie directe"
    if len(sources) > 1:
        note += " (seule la 1re sauvegarde a été utilisée)"
    return data, note


def backup_existing(dest: Path) -> Path | None:
    """Copie la sauvegarde déjà en place avant de l'écraser."""
    if not dest.is_file():
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = dest.with_name(dest.name + f".bak-{stamp}")
    shutil.copy2(dest, bak)
    return bak


def import_to_retroarch(
    system: str,
    file: str,
    sources: list[SaveFile],
    cfg_candidates: list[Path] | None = None,
) -> str:
    """Écrit la sauvegarde au format RetroArch et renvoie un message lisible."""
    ra_dir, why = retroarch_save_dir(cfg_candidates)
    if ra_dir is None:
        raise SaveError(why)
    data, note = to_retroarch_bytes(sources)
    if data is None:
        raise SaveError(note)
    dest = ra_dir / (Path(file).stem + "." + RETROARCH_EXT)
    ra_dir.mkdir(parents=True, exist_ok=True)
    bak = backup_existing(dest)
    dest.write_bytes(data)
    message = f"RetroArch : écrit {dest} ({note})"
    if bak is not None:
        message += f" — ancienne version copiée en {bak.name}"
    return message


def native_targets(
    system: str,
    file: str,
    roms_dir: str | None = None,
) -> list[Path]:
    """Emplacements plausibles pour l'émulateur natif (le premier dossier existant gagne)."""
    stem = Path(file).stem
    home = Path.home()
    out: list[Path] = []
    if system == "nds":
        melon = home / ".local/share/melonDS/saves"
        if melon.is_dir():
            out.append(melon / (stem + ".sav"))
        if roms_dir:
            out.append(Path(roms_dir).expanduser() / system / (stem + ".sav"))
    elif system == "n64":
        for base in (home / ".local/share/simple64/save", home / ".local/share/mupen64plus"):
            if base.is_dir():
                out += [base / (stem + ext) for ext in (".sra", ".eep", ".fla", ".mpk")]
        if roms_dir:
            out.append(Path(roms_dir).expanduser() / system / (stem + ".sra"))
    elif system == "psx":
        duck = home / ".local/share/duckstation/memcards"
        if duck.is_dir():
            out.append(duck / (stem + ".mcd"))
        if roms_dir:
            out.append(Path(roms_dir).expanduser() / system / (stem + ".mcd"))
    else:
        if roms_dir:
            out.append(Path(roms_dir).expanduser() / system / (stem + ".sav"))
    return out


def _split_n64(data: bytes) -> dict[str, bytes]:
    """Découpe un .srm combiné en fichiers .eep/.sra/.fla/.mpk (émulateurs natifs)."""
    out: dict[str, bytes] = {}
    if len(data) < N64_TOTAL:
        data = data + b"\x00" * (N64_TOTAL - len(data))
    eep = data[0x00000:0x00800]
    mpk = data[0x00800:0x20800]
    sra = data[0x20800:0x28800]
    fla = data[0x28800:0x48800]
    if any(eep):
        out[".eep"] = eep if any(eep[0x200:]) else eep[:0x200]
    if any(sra):
        out[".sra"] = sra
    if any(byte != 0xFF for byte in fla):
        out[".fla"] = fla
    if any(mpk):
        out[".mpk"] = mpk
    return out


def import_to_native(
    system: str,
    file: str,
    source: SaveFile,
    roms_dir: str | None = None,
) -> str:
    """Copie une sauvegarde vers l'émulateur natif et renvoie un message lisible."""
    targets = native_targets(system, file, roms_dir)
    if not targets:
        raise SaveError("Aucun emplacement d'émulateur natif trouvé — exporte une copie à la place")
    data = source.path.read_bytes()

    if system == "n64" and source.kind == "raw" and len(data) >= N64_TOTAL:
        parts = _split_n64(data)
        if not parts:
            raise SaveError("sauvegarde N64 vide")
        written: list[Path] = []
        for ext, blob in parts.items():
            dest = targets[0].parent / (Path(file).stem + ext)
            backup_existing(dest)
            dest.write_bytes(blob)
            written.append(dest)
        return "Émulateur natif : " + ", ".join(str(path) for path in written)

    dest = targets[0]
    note = ""
    if source.kind == "dsv":
        raw, why = _strip_dsv(data)
        if raw is not None:
            data = raw
            note = f" ({why})"
    dest.parent.mkdir(parents=True, exist_ok=True)
    bak = backup_existing(dest)
    dest.write_bytes(data)
    if bak is not None:
        note += f" — ancienne copie en {bak.name}"
    return f"Émulateur natif : {dest}{note}"


def export_copy(source: SaveFile, dest: Path) -> Path:
    """Copie la sauvegarde vers un fichier choisi par l'utilisateur."""
    dest = Path(dest).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.path, dest)
    return dest
