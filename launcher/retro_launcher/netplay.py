"""Netplay RetroArch — héberger / rejoindre une partie en ligne.

Le launcher ajoute les options netplay à la commande RetroArch :
  - héberger  : --host (+ relais MITM optionnel → aucun port à ouvrir)
  - rejoindre : --connect=ADRESSE --port=PORT

Un fichier « appendconfig » (dans le dossier de config du launcher, lisible même
depuis RetroArch en Flatpak — /tmp est privé dans le sandbox) porte le pseudo,
le port, le mot de passe et l'option relais.
"""
from __future__ import annotations

import socket
import subprocess
from pathlib import Path

from .config import config_dir, subprocess_env

DEFAULT_PORT = 55435


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def lan_address() -> str | None:
    """Adresse IP locale (celle utilisée pour sortir du réseau), si trouvable."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("1.1.1.1", 53))  # UDP : aucun paquet n'est envoyé
            return sock.getsockname()[0]
    except OSError:
        return None


def tailscale_address() -> str | None:
    """Adresse Tailscale (100.x) si la commande « tailscale » est disponible."""
    try:
        done = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
            env=subprocess_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    for line in done.stdout.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def candidate_addresses() -> list[tuple[str, str]]:
    """Adresses à donner à l'ami quand on héberge : [(libellé, adresse), …]."""
    found: list[tuple[str, str]] = []
    tail = tailscale_address()
    if tail:
        found.append(("Tailscale", tail))
    lan = lan_address()
    if lan and all(lan != ip for _tag, ip in found):
        found.append(("Réseau local", lan))
    return found


def write_appendconfig(
    *,
    nickname: str,
    port: int,
    password: str = "",
    use_relay: bool = False,
) -> Path:
    """Écrit le fichier de config partiel passé à RetroArch (--appendconfig)."""
    lines = [
        f'netplay_nickname = "{_escape(nickname)}"',
        f'netplay_ip_port = "{int(port)}"',
    ]
    if password:
        lines.append(f'netplay_password = "{_escape(password)}"')
    if use_relay:
        lines.append('netplay_use_mitm_server = "true"')
    path = config_dir() / "netplay-append.cfg"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
