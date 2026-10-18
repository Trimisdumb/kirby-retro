"""Trouver et copier les sauvegardes de jeu entre émulateurs et RetroArch.

RetroArch peut ranger ses sauvegardes par core (« saves/melonDS DS/… ») ou
les regrouper dans « saves/ ». Les émulateurs natifs écrivent d'autres
formats : melonDS en .sav, DeSmuME en .dsv, N64 en .eep/.sra/.fla/.mpk,
Dolphin en dossiers de titre (NAND Wii). On convertit au moment de la copie.

Au lancement, la sauvegarde la plus récente gagne (native → RetroArch ou
l'inverse) ; chaque écrasement garde l'ancienne version en .bak-<date>.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .detect import resolve_cfg_path, resolve_core_path, retroarch_cfg

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

# Extensions que RetroArch (et ses cores) utilisent pour les sauvegardes.
RA_SAVE_EXTS = (".srm", ".sav", ".dsv", ".eep", ".sra", ".fla", ".mpk", ".mcd", ".mcr")

# Noms de dossiers « par core » de RetroArch (retroarch.cfg → sort_savefiles).
_CORE_FOLDER_HINTS: dict[str, tuple[str, ...]] = {
    "nes": ("Mesen2", "FCEUmm", "Nestopia UE", "Mesen-S"),
    "snes": ("Snes9x", "bsnes", "Mesen-S"),
    "gb": ("Gambatte", "SameBoy", "Gearboy"),
    "gba": ("mGBA", "VBA-M", "gpSP"),
    "n64": ("Mupen64Plus-Next", "ParaLLEl N64"),
    "nds": ("melonDS DS", "melonDS", "DeSmuME", "DeSmuME 2015"),
    "psx": ("SwanStation", "PCSX-ReARmed", "Beetle PSX", "Beetle PSX HW"),
    "psp": ("PPSSPP",),
    "dreamcast": ("Flycast",),
    "segaMD": ("Genesis Plus GX", "PicoDrive"),
    "segaMS": ("Genesis Plus GX", "PicoDrive"),
    "segaGG": ("Genesis Plus GX", "PicoDrive"),
    "segaCD": ("Genesis Plus GX", "PicoDrive"),
    "sega32x": ("PicoDrive",),
    "segaSaturn": ("Beetle Saturn", "Kronos"),
    "atari2600": ("Stella 2014", "Stella"),
    "pce": ("Beetle PCE", "Beetle PCE Fast", "Beetle SuperGrafx"),
    "lynx": ("Beetle Lynx", "Handy"),
    "c64": ("VICE x64sc",),
    "vb": ("Beetle VB",),
    "cpc": ("Caprice32", "CrocoDS"),
    "apple2": ("AppleWin",),
    "pc88": ("QUASI88",),
    "pokemini": ("PokeMini",),
    "arcade": ("FBNeo",),
    "3ds": ("Azahar",),
}

# Nom de dossier quand le .info du core n'est pas disponible (Flatpak).
_CORE_DISPLAY = {
    "melondsds": "melonDS DS",
    "melonds": "melonDS",
    "desmume": "DeSmuME",
    "desmume2015": "DeSmuME 2015",
    "mupen64plus_next": "Mupen64Plus-Next",
    "parallel_n64": "ParaLLEl N64",
    "mesen2": "Mesen2",
    "mesen-s": "Mesen-S",
    "fceumm": "FCEUmm",
    "nestopia": "Nestopia UE",
    "snes9x": "Snes9x",
    "bsnes": "bsnes",
    "gambatte": "Gambatte",
    "sameboy": "SameBoy",
    "gearboy": "Gearboy",
    "mgba": "mGBA",
    "gpsp": "gpSP",
    "vba_next": "VBA-M",
    "genesis_plus_gx": "Genesis Plus GX",
    "picodrive": "PicoDrive",
    "swanstation": "SwanStation",
    "pcsx_rearmed": "PCSX-ReARmed",
    "mednafen_psx": "Beetle PSX",
    "mednafen_psx_hw": "Beetle PSX HW",
    "flycast": "Flycast",
    "ppsspp": "PPSSPP",
    "dolphin": "dolphin-emu",
    "stella2014": "Stella 2014",
    "stella": "Stella",
    "handy": "Handy",
    "mednafen_lynx": "Beetle Lynx",
    "vice_x64sc": "VICE x64sc",
    "mednafen_saturn": "Beetle Saturn",
    "kronos": "Kronos",
    "mednafen_pce": "Beetle PCE",
    "mednafen_pce_fast": "Beetle PCE Fast",
    "mednafen_supergrafx": "Beetle SuperGrafx",
    "mednafen_vb": "Beetle VB",
    "beetle_vb": "Beetle VB",
    "fbneo": "FBNeo",
    "cap32": "Caprice32",
    "crocods": "CrocoDS",
    "applewin": "AppleWin",
    "quasi88": "QUASI88",
    "pokemini": "PokeMini",
    "azahar": "Azahar",
    "citra2018": "Citra",
    "citra": "Citra",
}

_CODE_OK = re.compile(r"^[A-Z0-9]{6}$")


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

    def _dir_totals(self) -> tuple[int, float]:
        size, latest = 0, 0.0
        for item in self.path.rglob("*"):
            try:
                if item.is_file():
                    info = item.stat()
                    size += info.st_size
                    latest = max(latest, info.st_mtime)
            except OSError:
                continue
        return size, latest

    def size_ko(self) -> int:
        if self.path.is_dir():
            size, _ = self._dir_totals()
            return max(1, size // 1024)
        try:
            return max(1, self.path.stat().st_size // 1024)
        except OSError:
            return 0

    def date(self) -> str:
        mtime = self.mtime()
        if not mtime:
            return "?"
        stamp = _dt.datetime.fromtimestamp(mtime)
        return stamp.strftime("%d/%m/%Y %H:%M")

    def mtime(self) -> float:
        if self.path.is_dir():
            _, latest = self._dir_totals()
            return latest
        try:
            return self.path.stat().st_mtime
        except OSError:
            return 0.0


# ---------------------------------------------------------------------------
# dossier de sauvegardes de RetroArch

def _cfg_flag(text: str, key: str) -> bool:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(key):
            _, _, value = line.partition("=")
            return value.strip().strip('"').lower() in ("true", "1", "yes")
    return False


def retroarch_save_dir(cfg_candidates: list[Path] | None = None) -> tuple[Path | None, str]:
    """Dossier des sauvegardes de RetroArch, avec une explication lisible."""
    cfg, text = retroarch_cfg(cfg_candidates)
    if cfg is not None:
        value: str | None = None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("savefile_directory"):
                _, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                break
        resolved = resolve_cfg_path(value or "default", cfg.parent)
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


def _ra_search_dirs(base: Path) -> list[Path]:
    """« saves/ » puis ses sous-dossiers « par core » (melonDS DS, Mesen2…)."""
    out = [base]
    try:
        for item in sorted(base.iterdir()):
            if item.is_dir() and item.name != "dolphin-emu":
                out.append(item)
    except OSError:
        pass
    return out


def _core_display_name(core: str | Path) -> str | None:
    """Nom de dossier du core (display_name du .info, sinon table connue)."""
    path = Path(core)
    try:
        text = path.with_suffix(".info").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for line in text.splitlines():
        if line.startswith("display_name"):
            _, _, value = line.partition("=")
            value = value.strip().strip('"')
            if value:
                return value
    stem = path.stem
    if stem.endswith("_libretro"):
        stem = stem[: -len("_libretro")]
    return _CORE_DISPLAY.get(stem)


def retroarch_target_dir(
    system: str,
    file: str,
    cfg_candidates: list[Path] | None = None,
    cores_dir: str | None = None,
) -> tuple[Path | None, str]:
    """Dossier exact où RetroArch lira la sauvegarde (gère « trier par core »)."""
    base, why = retroarch_save_dir(cfg_candidates)
    if base is None:
        return None, why
    stem = Path(file).stem
    cfg, text = retroarch_cfg(cfg_candidates)
    sort = cfg is not None and _cfg_flag(text, "sort_savefiles_enable")
    subdirs = _ra_search_dirs(base)[1:]
    order = [*subdirs, base] if sort else [base, *subdirs]
    for folder in order:
        for ext in RA_SAVE_EXTS:
            if (folder / (stem + ext)).is_file():
                name = "saves" if folder == base else folder.name
                return folder, f"sauvegarde existante dans « {name} »"
    if not sort:
        return base, why
    by_content = _cfg_flag(text, "sort_savefiles_by_content_enable")
    hints = _CORE_FOLDER_HINTS.get(system, ())
    existing = [folder.name for folder in subdirs if folder.name in hints]
    name: str | None = None
    core = resolve_core_path(cores_dir, system) if cores_dir else None
    if core:
        display = _core_display_name(core)
        if display and (not existing or display in existing):
            name = display
    if not name and existing:
        name = existing[0]
    if name:
        target = base / name / stem if by_content else base / name
        return target, f"tri par core activé ({name})"
    return base, why


# ---------------------------------------------------------------------------
# Dolphin (NAND Wii) : les sauvegardes Wii sont des dossiers par jeu

def dolphin_roots() -> list[tuple[str, Path]]:
    home = Path.home()
    return [
        ("Dolphin", home / ".local/share/dolphin-emu"),
        ("Dolphin", home / ".dolphin-emu"),
        ("Dolphin (Flatpak)", home / ".var/app/org.DolphinEmu.dolphin-emu/data/dolphin-emu"),
    ]


def retroarch_dolphin_dir(cfg_candidates: list[Path] | None = None) -> Path | None:
    """Dossier « User » du Dolphin intégré à RetroArch (NAND Wii, mémoires GC)."""
    base, _why = retroarch_save_dir(cfg_candidates)
    if base is None:
        return None
    if base.is_dir():
        for sub in _ra_search_dirs(base):
            user = sub / "User"
            if (user / "Wii").is_dir() or (user / "GC").is_dir():
                return user
    return base / "dolphin-emu" / "User"


def _dolphin_title_roots(
    cfg_candidates: list[Path] | None = None, system: str = "wii"
) -> list[tuple[str, Path]]:
    sub = "Wii/title/00010000" if system == "wii" else "GC"
    out = [(label, root / sub) for label, root in dolphin_roots()]
    ra_user = retroarch_dolphin_dir(cfg_candidates)
    if ra_user is not None:
        out.append(("RetroArch (Dolphin)", ra_user / sub))
    return out


def wii_game_code(rom_path: Path | str | None) -> str | None:
    """Code du jeu Wii (« RSPE01 ») lu dans la ROM (.iso/.wbfs/.rvz, même en .zip)."""
    if not rom_path:
        return None
    path = Path(rom_path)
    if not path.is_file():
        return None
    try:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                members = [name for name in archive.namelist() if not name.endswith("/")]
                if not members:
                    return None
                with archive.open(members[0]) as handle:
                    return _code_from_stream(handle, Path(members[0]).suffix.lower())
        with path.open("rb") as handle:
            return _code_from_stream(handle, path.suffix.lower())
    except (OSError, zipfile.BadZipFile, EOFError):
        return None


def _code_from_stream(handle, ext: str) -> str | None:
    if ext == ".wbfs":
        head = handle.read(16)
        if len(head) < 12 or head[:4] != b"WBFS":
            return None
        shift = head[9]
        if not 1 <= shift <= 25:
            return None
        handle.seek(1 << shift)
        return _clean_code(handle.read(6))
    if ext == ".rvz":
        handle.seek(0x10)
        code = _clean_code(handle.read(6))
        if code:
            return code
        handle.seek(0)
    return _clean_code(handle.read(6))


def _clean_code(data: bytes) -> str | None:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return None
    return text if _CODE_OK.match(text) else None


def _title_label(name: str) -> str:
    """« 52484150 » → « RHAP » pour l'affichage."""
    try:
        text = bytes.fromhex(name).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return name
    return text if text.isprintable() and 3 <= len(text) <= 6 else name


def _find_dolphin_saves(
    system: str,
    cfg_candidates: list[Path] | None = None,
    rom_path: Path | str | None = None,
) -> list[SaveFile]:
    if system != "wii":
        return []
    code = wii_game_code(rom_path)
    # Dolphin nomme les dossiers de titre en hexadécimal : « RHAP01 » → « 52484150 ».
    want = code[:4].encode("ascii").hex().upper() if code else None
    found: list[SaveFile] = []
    for label, titles in _dolphin_title_roots(cfg_candidates, system):
        if not titles.is_dir():
            continue
        try:
            entries = sorted(item for item in titles.iterdir() if item.is_dir())
        except OSError:
            continue
        for entry in entries:
            if want and entry.name.upper() != want:
                continue
            found.append(
                SaveFile(entry, f"{label} · {_title_label(entry.name)}", "dolphin-title", system)
            )
    found.sort(key=lambda save: save.mtime(), reverse=True)
    return found


# ---------------------------------------------------------------------------
# données de la console Wii (Miis, réglages) : Dolphin natif → RetroArch

# La base des Miis et les réglages de la console vivent hors des dossiers de
# titre : sans elles, pas de Miis dans RetroArch et une langue anglaise.
WII_CONSOLE_FILES: tuple[Path, ...] = (
    Path("Wii/shared2/menu/FaceLib/RFL_DB.dat"),  # base des Miis
    Path("Wii/shared2/sys/SYSCONF"),  # langue et réglages du système Wii
)

_WII_LANGUAGES = {
    0: "japonais",
    1: "anglais",
    2: "allemand",
    3: "français",
    4: "espagnol",
    5: "italien",
    6: "néerlandais",
    7: "chinois simplifié",
    8: "chinois traditionnel",
    9: "coréen",
}


def wii_sysconf_language(path: Path) -> int | None:
    """Langue du système Wii réglée dans un SYSCONF (octet de « IPL.LNG »)."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    index = data.rfind(b"IPL.LNG")
    # L'octet d'en-tête 0x66 annonce une valeur d'un octet ; la langue suit le nom.
    if index < 1 or index + 8 > len(data) or data[index - 1] != 0x66:
        return None
    return data[index + 7]


def _sync_wii_console_files(source: Path, dest: Path) -> list[str]:
    """Copie Miis et réglages Wii de source vers dest (anciennes copies en .bak)."""
    notes: list[str] = []
    for rel in WII_CONSOLE_FILES:
        src_file = source / rel
        if not src_file.is_file():
            continue
        dst_file = dest / rel
        fresh = not dst_file.is_file()
        if not fresh:
            try:
                fresh = src_file.stat().st_mtime > dst_file.stat().st_mtime
            except OSError:
                fresh = False
        if not fresh and rel.name == "SYSCONF":
            # La langue système se règle dans Dolphin, pas dans RetroArch :
            # en cas de désaccord, c'est le choix de Dolphin qui gagne.
            lang_src = wii_sysconf_language(src_file)
            lang_dst = wii_sysconf_language(dst_file)
            fresh = lang_src is not None and lang_dst is not None and lang_src != lang_dst
        if not fresh:
            continue
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        bak = backup_existing(dst_file)
        shutil.copy2(src_file, dst_file)
        bak_note = f" — ancienne version en {bak.name}" if bak is not None else ""
        if rel.name == "RFL_DB.dat":
            notes.append(f"Miis copiés vers RetroArch{bak_note}")
        else:
            lang = wii_sysconf_language(src_file)
            language = _WII_LANGUAGES.get(lang, "?") if lang is not None else "?"
            notes.append(f"réglages Wii copiés vers RetroArch (langue : {language}){bak_note}")
    return notes


def sync_dolphin_console_data(cfg_candidates: list[Path] | None = None) -> list[str]:
    """Miis + réglages de la console : Dolphin natif → Dolphin de RetroArch.

    Sens unique exprès : dans l'autre direction, une base de Miis vide
    écraserait celle de ton Dolphin.
    """
    source = next((root for _label, root in dolphin_roots() if (root / "Wii").is_dir()), None)
    dest = retroarch_dolphin_dir(cfg_candidates) if source is not None else None
    if source is None or dest is None:
        return []
    return _sync_wii_console_files(source, dest)


# ---------------------------------------------------------------------------
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
    elif system == "nes":
        add("FCEUX", home / ".fceux/sav", (".sav",))
        add("Mesen2", home / ".local/share/Mesen2/Saves", (".srm", ".sav"))
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
        add("RetroArch", ra_dir, RA_SAVE_EXTS)
        for sub in _ra_search_dirs(ra_dir)[1:]:
            add(f"RetroArch ({sub.name})", sub, RA_SAVE_EXTS)

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
    rom_path: Path | str | None = None,
) -> list[SaveFile]:
    """Sauvegardes trouvées pour ce jeu (RetroArch par core + natifs), récentes d'abord."""
    if system in ("wii", "gamecube"):
        return _find_dolphin_saves(system, cfg_candidates, rom_path)
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


# ---------------------------------------------------------------------------
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


def _backup_dir(dest: Path) -> Path | None:
    """Copie un dossier de sauvegarde (Wii) déjà en place avant de l'écraser."""
    if not dest.is_dir():
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = dest.with_name(f"{dest.name}.bak-{stamp}")
    if bak.exists():
        shutil.rmtree(bak, ignore_errors=True)
    shutil.copytree(dest, bak)
    return bak


def _copy_dolphin_title(
    source: SaveFile,
    *,
    to_retroarch: bool,
    cfg_candidates: list[Path] | None = None,
) -> str:
    """Copie un dossier de sauvegarde Wii entre Dolphin natif et RetroArch."""
    code = source.path.name
    if to_retroarch:
        user_dir = retroarch_dolphin_dir(cfg_candidates)
        if user_dir is None:
            raise SaveError("Dossier Dolphin de RetroArch introuvable")
        label = "RetroArch"
    else:
        user_dir = next((root for _label, root in dolphin_roots() if root.is_dir()), None)
        if user_dir is None:
            raise SaveError("Dolphin (natif) introuvable — exporte une copie à la place")
        label = "Dolphin"
    dest = user_dir / "Wii/title/00010000" / code
    note = ""
    if dest.exists():
        bak = _backup_dir(dest)
        if bak is not None:
            shutil.rmtree(dest)
            note = f" — ancienne version copiée en {bak.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source.path, dest)
    return f"{label} : sauvegarde Wii {code} copiée vers {dest}{note}"


def import_to_retroarch(
    system: str,
    file: str,
    sources: list[SaveFile],
    cfg_candidates: list[Path] | None = None,
    cores_dir: str | None = None,
) -> str:
    """Écrit la sauvegarde là où RetroArch la lira, avec copie de secours."""
    if not sources:
        raise SaveError("aucune sauvegarde sélectionnée")
    source = sources[0]
    if source.kind == "dolphin-title":
        message = _copy_dolphin_title(source, to_retroarch=True, cfg_candidates=cfg_candidates)
        if system == "wii":
            try:
                notes = sync_dolphin_console_data(cfg_candidates)
            except Exception:  # noqa: BLE001 — la copie de sauvegarde a déjà réussi
                notes = []
            message = " · ".join([message, *notes]) if notes else message
        return message
    target_dir, why = retroarch_target_dir(system, file, cfg_candidates, cores_dir)
    if target_dir is None:
        raise SaveError(why)
    data, note = to_retroarch_bytes(sources)
    if data is None:
        raise SaveError(note)
    dest = target_dir / (Path(file).stem + "." + RETROARCH_EXT)
    target_dir.mkdir(parents=True, exist_ok=True)
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
    if source.kind == "dolphin-title":
        return _copy_dolphin_title(source, to_retroarch=False)
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
    if source.path.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source.path, dest)
        return dest
    shutil.copy2(source.path, dest)
    return dest


# ---------------------------------------------------------------------------
# synchronisation au lancement

def auto_sync_before_launch(
    config: dict,
    system: str,
    file: str,
    rom_path: Path | str | None = None,
    to_retroarch: bool = True,
    cfg_candidates: list[Path] | None = None,
) -> str | None:
    """Avant un lancement : la sauvegarde la plus récente gagne.

    native → RetroArch (ou l'inverse), avec copie de secours. Ne bloque jamais
    le lancement : en cas de problème, on continue sans rien dire.
    """
    if not config.get("auto_sync_saves", True):
        return None
    try:
        roms_dir = (config.get("roms_dir") or "").strip() or None
        cores_dir = str((config.get("retroarch") or {}).get("cores_dir") or "") or None
        saves = find_saves(system, file, roms_dir, cfg_candidates, rom_path=rom_path)
        natives = [save for save in saves if not save.source.startswith("RetroArch")]
        retro = [save for save in saves if save.source.startswith("RetroArch")]
        if to_retroarch:
            console_notes: list[str] = []
            if system == "wii":
                # Miis et réglages de la console : indépendants des sauvegardes.
                try:
                    console_notes = sync_dolphin_console_data(cfg_candidates)
                except Exception:  # noqa: BLE001
                    console_notes = []
            save_note = ""
            if natives and not (retro and retro[0].mtime() >= natives[0].mtime()):
                import_to_retroarch(
                    system, file, natives, cfg_candidates=cfg_candidates, cores_dir=cores_dir
                )
                save_note = f"Sauvegarde importée vers RetroArch ({natives[0].source})"
            parts = [note for note in (save_note, *console_notes) if note]
            return " · ".join(parts) if parts else None
        if not retro:
            return None
        if natives and natives[0].mtime() >= retro[0].mtime():
            return None
        import_to_native(system, file, retro[0], roms_dir=roms_dir)
        return "Sauvegarde RetroArch exportée vers l'émulateur natif"
    except Exception:  # noqa: BLE001
        return None
