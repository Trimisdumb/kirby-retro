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
        "music": True,
        "music_file": "",
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
