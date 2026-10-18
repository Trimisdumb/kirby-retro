"""Enregistrement du protocole kirbyretro:// (Linux / Windows)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCHEME = "kirbyretro"


def launcher_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _frozen_exe() -> str | None:
    """Chemin du binaire autonome (PyInstaller), ou None en mode source."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return None


def _install_hint() -> str:
    if _frozen_exe() is not None:
        return "kirby-retro-launcher install-protocol"
    return "run.bat install-protocol" if sys.platform == "win32" else "./run.sh install-protocol"


# --------------------------------------------------------------------- Linux

def _desktop_escape(value: str) -> str:
    """Échappe une valeur pour un argument quoté d'un fichier .desktop."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")


def _linux_desktop_path() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    apps = data_home / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    return apps / f"{SCHEME}.desktop"


def install_linux() -> str:
    exe = _frozen_exe()
    if exe:
        exec_line = f'"{_desktop_escape(exe)}" play --url %u'
    else:
        run_sh = launcher_root() / "run.sh"
        if not run_sh.is_file():
            raise FileNotFoundError(f"run.sh introuvable : {run_sh}")
        try:  # pas indispensable (on passe par bash) mais pratique pour ./run.sh direct
            run_sh.chmod(run_sh.stat().st_mode | 0o111)
        except OSError:
            pass
        exec_line = f'bash "{_desktop_escape(str(run_sh))}" play --url %u'
    desktop = _linux_desktop_path()
    desktop.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Kirby Retro Launcher",
                "Comment=Ouvrir un jeu retro.kirbytrim.buzz en natif (RetroArch / melonDS)",
                f"Exec={exec_line}",
                f"MimeType=x-scheme-handler/{SCHEME};",
                "Icon=applications-games",
                "Terminal=false",
                "Categories=Game;",
                "NoDisplay=false",
                "StartupNotify=true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # Nettoie les gestionnaires parasites (ex. créés par Wine lors de tests)
    stale = list(desktop.parent.glob("wine-protocol-*kirbyretro*.desktop"))
    for f in stale:
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass

    for cmd in (
        ["xdg-mime", "default", desktop.name, f"x-scheme-handler/{SCHEME}"],
        ["update-desktop-database", str(desktop.parent)],
    ):
        try:
            subprocess.run(cmd, capture_output=True, timeout=20, check=False)
        except OSError:
            pass  # outils absents : le fichier .desktop suffit dans la plupart des environnements

    note = f" ({len(stale)} entrée(s) Wine parasite(s) nettoyée(s))" if stale else ""
    return (
        f"Protocole {SCHEME}:// enregistré → {desktop}{note}\n"
        f"Test : xdg-open \"{SCHEME}://play?system=nes&file=nestest.nes\""
    )


# ------------------------------------------------------------------- Windows

def _windows_command() -> str:
    exe = _frozen_exe()
    if exe:
        return f'"{exe}" play --url "%1"'
    run_bat = launcher_root() / "run.bat"
    # Forme conseillée par Microsoft pour lancer un .bat depuis le registre :
    # cmd /c ""chemin\run.bat" play --url "%1""
    return f'cmd /c ""{run_bat}" play --url "%1""'


def install_windows() -> str:
    import winreg  # disponible uniquement sous Windows

    base = rf"Software\Classes\{SCHEME}"

    def register(root: int) -> None:
        with winreg.CreateKey(root, base) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Kirby Retro Launcher")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(root, base + r"\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _windows_command())

    register(winreg.HKEY_CURRENT_USER)
    machine = False
    try:
        register(winreg.HKEY_LOCAL_MACHINE)
        machine = True
    except OSError:
        pass  # pas administrateur : HKCU suffit, c'est le cas normal

    scope = "HKCU + HKLM" if machine else "HKCU (aucun droit admin requis)"
    return f"Protocole {SCHEME}:// enregistré ({scope})."


def _status_windows() -> str:
    try:
        import winreg

        for root, name in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
            try:
                with winreg.OpenKey(root, rf"Software\Classes\{SCHEME}\shell\open\command") as key:
                    command, _kind = winreg.QueryValueEx(key, "")
                if command:
                    return f"[OK] enregistré ({name}) → {command}"
            except OSError:
                continue
        return f"[--] non enregistré — lance « {_install_hint()} »"
    except ImportError:
        return "[--] hors Windows"


# ---------------------------------------------------------------- interface

def install_protocol() -> str:
    if sys.platform == "win32":
        return install_windows()
    if sys.platform == "darwin":
        return (
            "macOS : enregistrement automatique non pris en charge pour l'instant.\n"
            "Voir la section macOS du README (Automator → « Ouvrir un document »)."
        )
    return install_linux()


def status() -> str:
    """État de l'enregistrement, pour le diagnostic."""
    if sys.platform == "win32":
        return _status_windows()
    if sys.platform == "darwin":
        return "[--] vérification automatique non prise en charge (macOS)"
    desktop = _linux_desktop_path()
    if not desktop.is_file():
        return f"[--] non enregistré — lance « {_install_hint()} »"
    registered = "?"
    try:
        out = subprocess.run(
            ["xdg-mime", "query", "default", f"x-scheme-handler/{SCHEME}"],
            capture_output=True,
            timeout=10,
            check=False,
            text=True,
        )
        registered = (out.stdout or "").strip() or "?"
    except OSError:
        registered = desktop.name
    flag = "[OK]" if registered == desktop.name else "[!!]"
    return f"{flag} fichier {desktop.name} (gestionnaire : {registered or '?'})"
