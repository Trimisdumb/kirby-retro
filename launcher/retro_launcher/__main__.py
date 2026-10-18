"""
Point d'entrée :
  python -m retro_launcher              → interface graphique
  python -m retro_launcher play SYSTEM FILE
  python -m retro_launcher play --url "kirbyretro://play?system=nds&file=game.nds"
  python -m retro_launcher install-protocol   → associe les liens kirbyretro://
  python -m retro_launcher doctor             → diagnostic complet
"""
from __future__ import annotations

import argparse
import sys
import urllib.parse

from . import __version__
from .config import load_config
from .detect import autofill


def parse_protocol(url: str) -> tuple[str, str]:
    """kirbyretro://play?system=nds&file=foo.nds"""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    # aussi path style kirbyretro://play/nds/file
    system = (qs.get("system") or [None])[0]
    file = (qs.get("file") or [None])[0]
    if not system and parsed.path:
        parts = [p for p in parsed.path.split("/") if p and p != "play"]
        if len(parts) >= 2:
            system, file = parts[0], "/".join(parts[1:])
    if not system or not file:
        raise SystemExit(f"URL invalide : {url}")
    return system, urllib.parse.unquote(file)


def cmd_play(system: str, file: str, *, browser: bool = False) -> int:
    config = autofill(load_config())
    from .feedback import run_console, run_with_feedback

    if browser:
        return run_with_feedback(config, system, file)
    return run_console(config, system, file)


def _force_utf8_console() -> None:
    """Évite les UnicodeEncodeError (console Windows cp1252, sortie redirigée, locale C)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _launch_gui() -> int:
    try:
        from .gui import run_gui

        run_gui()
    except ImportError as exc:
        print(
            "Interface graphique indisponible : tkinter est manquant.\n"
            "  Fedora : sudo dnf install python3-tkinter\n"
            "  Debian/Ubuntu : sudo apt install python3-tk\n"
            "  Arch : sudo pacman -S tk\n\n"
            f"Détail : {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    parser = argparse.ArgumentParser(prog="retro_launcher", description="Launcher natif Kirby Retro")
    parser.add_argument("--version", action="version", version=f"Kirby Retro Launcher {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    play = sub.add_parser("play", help="Lancer un jeu")
    play.add_argument("system", nargs="?", help="id console (nds, n64, …)")
    play.add_argument("file", nargs="?", help="nom de fichier ROM")
    play.add_argument("--url", nargs="?", help="URL kirbyretro://… (sans valeur : ouvre l'interface)")

    sub.add_parser("gui", help="Ouvrir l'interface (défaut)")
    sub.add_parser("install-protocol", help="Associer les liens kirbyretro:// au launcher")
    sub.add_parser("doctor", help="Diagnostic : config, RetroArch, cores, site, protocole")

    args = parser.parse_args(argv)

    if args.cmd == "install-protocol":
        from .protocol import install_protocol

        print(install_protocol())
        return 0

    if args.cmd == "doctor":
        from .doctor import collect

        print(collect())
        return 0

    if args.cmd == "play":
        url = (args.url or "").strip()
        if url:
            try:
                system, file = parse_protocol(url)
            except SystemExit as exc:
                from .feedback import notify_error

                notify_error(str(exc))
                return 1
            return cmd_play(system, file, browser=True)
        if args.system and args.file:
            return cmd_play(args.system, args.file)
        # Lancé sans cible (ex. clic depuis le menu applications) → interface
        return _launch_gui()

    # GUI par défaut
    return _launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
