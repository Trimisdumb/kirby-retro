"""Client HTTP vers l'API du site (stdlib uniquement)."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def fetch_library(site_url: str, timeout: float = 30.0) -> dict[str, Any]:
    base = site_url.rstrip("/")
    url = f"{base}/api/library"
    req = urllib.request.Request(url, headers={"User-Agent": "KirbyRetroLauncher/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def rom_url(site_url: str, system: str, file: str) -> str:
    base = site_url.rstrip("/")
    return f"{base}/roms/{urllib.parse.quote(system)}/{urllib.parse.quote(file)}"


def download_rom(site_url: str, system: str, file: str, dest: str, timeout: float = 600.0) -> None:
    url = rom_url(site_url, system, file)
    req = urllib.request.Request(url, headers={"User-Agent": "KirbyRetroLauncher/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
