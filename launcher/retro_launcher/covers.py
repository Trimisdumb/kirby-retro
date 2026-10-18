"""Jaquettes : cache local, dossier ROMs, téléchargement auto depuis le site."""
from __future__ import annotations

import queue
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from .config import cache_dir

# UA « navigateur » : Cloudflare (erreur 1010) refuse les UA exotiques.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 "
    "Firefox/128.0 KirbyRetroLauncher/1.5"
)
TIMEOUT = 25


def covers_cache_dir() -> Path:
    return cache_dir() / "covers"


class CoverManager:
    """Résout les jaquettes (dossier ROMs → cache → téléchargement)."""

    def __init__(self, site_url: str = "", roms_dir: str = "") -> None:
        self.site_url = (site_url or "").rstrip("/")
        self.roms_dir = (roms_dir or "").strip()
        self.cache = covers_cache_dir()
        self.results: queue.Queue[tuple[str, Path | None]] = queue.Queue()
        self._lock = threading.Lock()
        self._inflight: set[str] = set()

    @staticmethod
    def key(system: str, file: str) -> str:
        return f"{system}/{file}"

    def update_config(self, site_url: str, roms_dir: str) -> None:
        self.site_url = (site_url or "").rstrip("/")
        self.roms_dir = (roms_dir or "").strip()

    # résolution
    def resolve(self, system: str, file: str, cover: str = "") -> tuple[str, Path | None]:
        """('ready', chemin) | ('pending', None) | ('none', None)."""
        local = self._local_path(system, file)
        if local:
            return ("ready", local)
        cached = self._cache_path(system, file)
        if cached.is_file():
            return ("ready", cached)
        if not cover:
            return ("none", None)
        key = self.key(system, file)
        with self._lock:
            if key in self._inflight:
                return ("pending", None)
            self._inflight.add(key)
        threading.Thread(target=self._download, args=(system, file, cover), daemon=True).start()
        return ("pending", None)

    def _cache_path(self, system: str, file: str) -> Path:
        return self.cache / system / (Path(file).stem + ".png")

    def _local_path(self, system: str, file: str) -> Path | None:
        """Jaquettes locales : dossier ROMs (convention du site) ou à côté du jeu."""
        if not self.roms_dir:
            return None
        root = Path(self.roms_dir).expanduser()
        stem = Path(file).stem
        candidates = (
            root / "covers" / system / (stem + ".png"),
            root / "covers" / system / (file + ".png"),
            root / system / "covers" / (stem + ".png"),
            root / system / (stem + ".png"),
            root / system / (file + ".png"),
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _download(self, system: str, file: str, cover: str) -> None:
        key = self.key(system, file)
        result: Path | None = None
        try:
            url = cover
            if not url.lower().startswith(("http://", "https://")):
                if not url.startswith("/"):
                    url = "/" + url
                url = self.site_url + url
            url = urllib.parse.quote(url, safe=":/?&=#%+,()!'-_.~")
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
            if data and len(data) > 100:
                dest = self._cache_path(system, file)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                result = dest
        except Exception:  # noqa: BLE001
            result = None
        finally:
            with self._lock:
                self._inflight.discard(key)
            self.results.put((key, result))
