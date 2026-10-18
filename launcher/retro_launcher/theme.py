"""Thème rétro-arcade : palette néon, polices pixel, helpers canvas."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path

# Palette
BG_DARK = "#0b0416"
BG_DEEP = "#12071f"
BG_HEADER = "#170b2a"
BG_PANEL = "#1a0d2e"
BG_PANEL_HI = "#261240"
BTN_DARK = "#0e0619"
BORDER_DIM = "#3a1f5c"
BORDER_MID = "#5a2ea6"
NEON_PURPLE = "#a34ef7"
NEON_PINK = "#ff4fd8"
NEON_ORANGE = "#ff8a2a"
NEON_YELLOW = "#ffd166"
NEON_CYAN = "#4ff0ff"
NEON_GREEN = "#68ffa0"
RED = "#ff6b6b"
TXT = "#f1e7ff"
TXT_DIM = "#a58fc4"
TXT_DARK = "#6a5590"

# dégradé de fond (haut → bas)
GRADIENT = [
    (0.0, "#150627"),
    (0.45, "#26093a"),
    (0.75, "#3d0f3d"),
    (1.0, "#4a1a33"),
]

FONT_TITLE = "Press Start 2P"
FONT_BODY = "VT323"
FONT_FALLBACK = "Courier"


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


# Polices pixel
def _system_font_dir() -> Path | None:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "Microsoft" / "Windows" / "Fonts"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Fonts"
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "fonts" / "kirby-retro-launcher"


def ensure_fonts() -> None:
    """Installe les polices pixel sur le système (une seule fois).

    À appeler AVANT de créer la fenêtre Tk pour que fontconfig les voie.
    """
    src = assets_dir() / "fonts"
    dst = _system_font_dir()
    if not src.is_dir() or dst is None:
        return
    try:
        dst.mkdir(parents=True, exist_ok=True)
        copied = False
        for ttf in sorted(src.glob("*.ttf")):
            target = dst / ttf.name
            if not target.is_file() or target.stat().st_size != ttf.stat().st_size:
                shutil.copy2(ttf, target)
                copied = True
        if copied and sys.platform.startswith("linux"):
            subprocess.run(
                ["fc-cache", "-f", str(dst)],
                capture_output=True,
                timeout=20,
                check=False,
            )
        if copied and sys.platform == "win32":
            try:
                import ctypes

                gdi32 = ctypes.windll.gdi32
                for ttf in sorted(src.glob("*.ttf")):
                    gdi32.AddFontResourceExW(str(dst / ttf.name), 0x10, 0)
            except Exception:  # noqa: BLE001
                pass
    except OSError:
        pass


def resolve_fonts(root) -> tuple[str, str]:
    """(police titres, police corps) réellement disponibles dans Tk."""
    try:
        families = set(root.tk.call("font", "families"))
    except Exception:  # noqa: BLE001
        families = set()
    title = FONT_TITLE if FONT_TITLE in families else FONT_FALLBACK
    body = FONT_BODY if FONT_BODY in families else title
    return title, body


# Couleurs / canvas
def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


def mix(c1: str, c2: str, t: float) -> str:
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(t: float) -> str:
    t = min(1.0, max(0.0, t))
    for i in range(len(GRADIENT) - 1):
        t0, c0 = GRADIENT[i]
        t1, c1 = GRADIENT[i + 1]
        if t <= t1 or i == len(GRADIENT) - 2:
            span = (t1 - t0) or 1.0
            return mix(c0, c1, (t - t0) / span)
    return GRADIENT[-1][1]


def rounded_rect(canvas, x1, y1, x2, y2, r=10, **kw):
    """Rectangle aux coins arrondis (polygon lissé)."""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def draw_gradient(canvas, x1, y1, x2, y2, *, tags=("bgfx",), band=3) -> None:
    height = max(1, y2 - y1)
    y = y1
    while y < y2:
        t = (y - y1) / height
        canvas.create_rectangle(
            x1, y, x2, min(y2, y + band) + 1,
            fill=gradient_color(t), outline="", tags=tags,
        )
        y += band


def draw_scanlines(canvas, x1, y1, x2, y2, *, tags=("bgfx",), step=4) -> None:
    y = y1
    while y < y2:
        canvas.create_line(x1, y, x2, y, fill="#000000", stipple="gray25", tags=tags)
        y += step


# Widgets
def neon_label(parent, text, command, *, font, fg, bg,
               hover_fg=BG_DARK, hover_bg=NEON_YELLOW, padx=16, pady=8):
    """Bouton plat style néon (Label cliquable, glow au survol)."""
    lbl = tk.Label(parent, text=text, font=font, fg=fg, bg=bg,
                   padx=padx, pady=pady, cursor="hand2", bd=0, highlightthickness=0)
    lbl.bind("<Enter>", lambda _e: lbl.configure(fg=hover_fg, bg=hover_bg))
    lbl.bind("<Leave>", lambda _e: lbl.configure(fg=fg, bg=bg))
    lbl.bind("<Button-1>", lambda _e: command())
    return lbl


def styled_entry(parent, textvariable, *, font, width=24):
    """Entrée avec liseré néon. Retourne (conteneur, entrée)."""
    box = tk.Frame(parent, bg=BORDER_MID, padx=1, pady=1)
    entry = tk.Entry(box, textvariable=textvariable, font=font, width=width,
                     bg=BTN_DARK, fg=TXT, insertbackground=NEON_CYAN,
                     relief="flat", bd=0, highlightthickness=0)
    entry.pack(fill="both", padx=5, pady=4)
    return box, entry
