"""Chargement / sauvegarde de la configuration du launcher."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "KirbyRetroLauncher"


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


# Magasins de certificats usuels (OpenSSL embarqué : chemins Debian compilés en dur).
_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Ubuntu, Fedora, Arch…
    "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL / Fedora (classique)
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora / RHEL (ca-trust)
    "/etc/ssl/ca-bundle.pem",  # openSUSE
    "/etc/ssl/cert.pem",  # Alpine, macOS
)


def ensure_ca_bundle() -> None:
    """Binaire autonome : l'OpenSSL embarqué ne connaît que les chemins de la
    machine de construction (Debian). On pointe SSL_CERT_FILE vers un magasin
    présent sur la machine, sinon vers la copie fournie dans le binaire."""
    if not getattr(sys, "frozen", False) or not sys.platform.startswith("linux"):
        return
    if os.environ.get("SSL_CERT_FILE"):
        return
    candidates = list(_CA_BUNDLES)
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidates.append(str(Path(meipass) / "certs" / "ca-certificates.crt"))
    for candidate in candidates:
        if Path(candidate).is_file():
            os.environ["SSL_CERT_FILE"] = candidate
            return


def subprocess_env() -> dict[str, str]:
    """Environnement des outils lancés (flatpak, RetroArch, xdg-mime…).

    L'exécutable autonome exporte LD_LIBRARY_PATH vers ses bibliothèques
    embarquées (Debian) : les binaires système les prendraient à tort, d'où des
    erreurs de version d'OpenSSL sur Fedora, Arch… On les lance donc sans."""
    env = dict(os.environ)
    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        env.pop("LD_LIBRARY_PATH", None)
    return env


def default_config() -> dict[str, Any]:
    return {
        "site_url": "https://retro.kirbytrim.buzz",
        "roms_dir": "",
        "download_missing_roms": True,
        "auto_sync_saves": True,
        "retroarch": {"path": "", "cores_dir": ""},
        "emulators": {},
        "prefer_native_for": ["nds", "n64", "psx"],
        "netplay": {"nickname": "", "port": 55435, "last_host": "", "use_relay": False},
    }


def load_config() -> dict[str, Any]:
    path = config_path()
    data = default_config()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
                if "retroarch" in raw and isinstance(raw["retroarch"], dict):
                    data["retroarch"] = {**default_config()["retroarch"], **raw["retroarch"]}
                if "netplay" in raw and isinstance(raw["netplay"], dict):
                    data["netplay"] = {**default_config()["netplay"], **raw["netplay"]}
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save_config(data: dict[str, Any]) -> None:
    path = config_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
