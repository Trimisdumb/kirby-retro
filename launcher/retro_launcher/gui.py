"""Interface Tkinter du launcher : cartes avec jaquettes, chiptune, netplay.

Habillage rétro : fenêtre sans bordure, dégradé violet/orangé avec scanlines,
polices pixel, recherche et filtres par console.
"""
from __future__ import annotations

import math
import threading
import tkinter as tk
import tkinter.font as tkfont
import unicodedata
from pathlib import Path
from queue import Empty
from tkinter import ttk
from typing import Any

from . import __version__
from . import saves as saves_mod
from .api import fetch_library
from .config import load_config, save_config
from .covers import CoverManager
from .detect import autofill, find_native
from .launch import LaunchError, launch_game, launch_netplay
from .music import MusicPlayer
from .netplay import DEFAULT_PORT, candidate_addresses
from .protocol import install_protocol
from .theme import (
    BG_DARK,
    BG_DEEP,
    BG_HEADER,
    BG_PANEL,
    BG_PANEL_HI,
    BORDER_DIM,
    BORDER_MID,
    BTN_DARK,
    NEON_CYAN,
    NEON_GREEN,
    NEON_ORANGE,
    NEON_PINK,
    NEON_PURPLE,
    NEON_YELLOW,
    RED,
    TXT,
    TXT_DARK,
    TXT_DIM,
    draw_gradient,
    draw_scanlines,
    neon_label,
    rounded_rect,
    styled_entry,
)

CARD_W = 200
CARD_H = 292
CARD_GAP = 16
GRID_PAD = 18
COVER_BOX = 176
MAX_COLS = 6
TITLE_CHARS = 24


def _wrap(text: str, width: int = TITLE_CHARS, max_lines: int = 3) -> str:
    words = str(text).split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) == max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if not lines:
        lines = [str(text)[:width]]
    used = sum(len(line) + 1 for line in lines)
    if used < len(str(text)):
        lines[-1] = lines[-1][: max(1, width - 1)] + "…"
    return "\n".join(lines[:max_lines])


def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(text).lower()) if not unicodedata.combining(c)
    )


class LauncherApp(tk.Tk):
    def __init__(self, title_family: str = "Courier", body_family: str = "Courier") -> None:
        super().__init__()
        self.overrideredirect(True)
        self.configure(bg="#4a1f7a")
        self.title(f"Kirby Retro Launcher v{__version__}")

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self._win_w = min(1280, max(940, sw - 80))
        self._win_h = min(820, max(620, sh - 80))
        self.geometry(
            f"{self._win_w}x{self._win_h}"
            f"+{max(0, (sw - self._win_w) // 2)}+{max(0, (sh - self._win_h) // 2 - 24)}"
        )

        self.config_data = autofill(load_config())
        self.library: dict[str, Any] | None = None
        self.covers = CoverManager(
            str(self.config_data.get("site_url") or ""),
            str(self.config_data.get("roms_dir") or ""),
        )
        self.music = MusicPlayer(self.config_data)

        self._cards: list[dict[str, Any]] = []
        self._thumbs: dict[str, tk.PhotoImage] = {}
        self._chip_widgets: dict[str, tk.Label] = {}
        self._head_windows: list[tuple[int, tk.Label]] = []
        self._filter_system = "all"
        self._selected: int | None = None
        self._hover: int | None = None
        self._scroll = 0
        self._scroll_max = 0
        self._sb: tuple[int, int, int] | None = None
        self._sb_drag = False
        self._sb_grab = 0
        self._busy = False
        self._music_synced = False
        self._last_size = (0, 0)
        self._drag_origin: tuple[int, int] | None = None

        self._status = tk.StringVar(value="Allumage de la borne…")
        self._search = tk.StringVar()

        self.f_title = tkfont.Font(family=title_family, size=13, weight="bold")
        self.f_title_sm = tkfont.Font(family=title_family, size=8)
        self.f_card = tkfont.Font(family=title_family, size=7)
        self.f_body = tkfont.Font(family=body_family, size=16)
        self.f_small = tkfont.Font(family=body_family, size=13)
        self.f_badge = tkfont.Font(family=body_family, size=12)

        self._build()
        threading.Thread(target=self._music_prepare, daemon=True).start()
        self.after(150, self.refresh_library)
        self.after(300, self._poll)
        self.bind("<F5>", lambda _e: self.refresh_library())
        self.bind("<Return>", lambda _e: self.play_selected())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # construction
    def _build(self) -> None:
        outer = tk.Frame(self, bg="#4a1f7a")
        outer.pack(fill="both", expand=True)
        glow2 = tk.Frame(outer, bg="#8a2be2")
        glow2.pack(fill="both", expand=True, padx=2, pady=2)
        glow3 = tk.Frame(glow2, bg=NEON_PINK)
        glow3.pack(fill="both", expand=True, padx=1, pady=1)
        deep = tk.Frame(glow3, bg="#201038")
        deep.pack(fill="both", expand=True, padx=1, pady=1)
        root = tk.Frame(deep, bg=BG_DARK)
        root.pack(fill="both", expand=True)
        self._build_header(root)
        self._build_toolbar(root)
        self._build_grid(root)
        self._build_footer(root)

    def _build_header(self, parent) -> None:
        self._head = tk.Canvas(parent, height=54, bg=BG_HEADER, highlightthickness=0, bd=0)
        self._head.pack(fill="x")
        head = self._head
        head.bind("<Button-1>", self._drag_start)
        head.bind("<B1-Motion>", self._drag_move)
        head.create_text(24, 30, text="KIRBY RETRO LAUNCHER", font=self.f_title,
                         fill="#5c2488", anchor="w")
        self._title_id = head.create_text(22, 28, text="KIRBY RETRO LAUNCHER",
                                          font=self.f_title, fill=NEON_ORANGE, anchor="w")
        title_w = self.f_title.measure("KIRBY RETRO LAUNCHER")
        head.create_text(30 + title_w, 30, text=f"v{__version__}", font=self.f_small,
                         fill=TXT_DIM, anchor="w")
        self._btn_close = self._head_text_button("X", RED, self.on_close)
        self._btn_min = self._head_text_button("-", TXT_DIM, self.minimize)
        self._btn_music = self._head_text_button("MUSIQUE …", TXT_DIM, self.toggle_music)
        self._btn_cfg = self._head_text_button("REGLAGES", NEON_CYAN, self.open_settings)
        head.bind("<Configure>", self._place_head)

    def _head_text_button(self, text: str, fg: str, command) -> tk.Label:
        lbl = tk.Label(self._head, text=text, font=self.f_small, fg=fg, bg=BG_HEADER,
                       padx=9, pady=3, cursor="hand2", bd=0, highlightthickness=0)
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>", lambda _e: lbl.configure(bg=BG_PANEL_HI))
        lbl.bind("<Leave>", lambda _e: lbl.configure(bg=BG_HEADER))
        window_id = self._head.create_window(-999, -999, window=lbl)
        self._head_windows.append((window_id, lbl))
        return lbl

    def _place_head(self, _event=None) -> None:
        x = self._head.winfo_width() - 28
        for window_id, lbl in self._head_windows:
            self._head.coords(window_id, x, 28)
            x -= lbl.winfo_reqwidth() + 6

    def _build_toolbar(self, parent) -> None:
        bar = tk.Frame(parent, bg=BG_DEEP, padx=14, pady=8)
        bar.pack(fill="x")
        tk.Label(bar, text="RECHERCHE :", font=self.f_badge, fg=NEON_PINK, bg=BG_DEEP,
                 padx=6).pack(side="left")
        box, entry = styled_entry(bar, self._search, font=self.f_body, width=22)
        box.pack(side="left")
        entry.bind("<KeyRelease>", self._on_search)
        self._search_entry = entry
        self._chips = tk.Frame(bar, bg=BG_DEEP)
        self._chips.pack(side="left", fill="x", expand=True, padx=(18, 8))
        neon_label(bar, "ACTUALISER", self.refresh_library, font=self.f_badge, fg=BG_DARK,
                   bg=NEON_CYAN, hover_bg=NEON_YELLOW, padx=12, pady=6).pack(side="right")

    def _build_grid(self, parent) -> None:
        wrap = tk.Frame(parent, bg=BG_DARK)
        wrap.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self.canvas = tk.Canvas(wrap, bg=BG_DARK, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        canvas = self.canvas
        canvas.bind("<MouseWheel>", self._on_wheel)
        canvas.bind("<Button-4>", lambda _e: self._scroll_by(-72))
        canvas.bind("<Button-5>", lambda _e: self._scroll_by(72))
        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<Leave>", lambda _e: self._set_hover(None))
        canvas.bind("<ButtonPress-1>", self._on_press)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_sb_drag", False))
        canvas.bind("<Double-Button-1>", self._on_double)
        canvas.bind("<Button-3>", self._on_right)
        canvas.bind("<Configure>", self._on_resize)

    def _build_footer(self, parent) -> None:
        foot = tk.Frame(parent, bg=BG_HEADER, padx=14, pady=10)
        foot.pack(fill="x", padx=12, pady=(8, 12))
        self._btn_play = neon_label(foot, "JOUER", self.play_selected, font=self.f_title_sm,
                                    fg=BG_DARK, bg=NEON_ORANGE, hover_bg=NEON_YELLOW,
                                    padx=22, pady=10)
        self._btn_play.pack(side="left")
        self._btn_net = neon_label(foot, "EN LIGNE", self.netplay_selected, font=self.f_title_sm,
                                   fg=TXT, bg=NEON_PURPLE, hover_fg=BG_DARK, hover_bg=NEON_PINK,
                                   padx=22, pady=10)
        self._btn_net.pack(side="left", padx=10)
        self._btn_saves = neon_label(foot, "SAUVEGARDES", self.saves_selected, font=self.f_title_sm,
                                     fg=TXT, bg=BG_PANEL_HI, hover_fg=BG_DARK, hover_bg=NEON_CYAN,
                                     padx=16, pady=10)
        self._btn_saves.pack(side="left")
        tk.Label(foot, textvariable=self._status, font=self.f_body, fg=TXT_DIM, bg=BG_HEADER,
                 anchor="e").pack(side="right", fill="x", expand=True, padx=(16, 0))

    # fenêtre (sans bordure)
    def _drag_start(self, event) -> None:
        self._drag_origin = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_move(self, event) -> None:
        if self._drag_origin:
            self.geometry(
                f"+{event.x_root - self._drag_origin[0]}+{event.y_root - self._drag_origin[1]}"
            )

    def minimize(self) -> None:
        try:
            self.overrideredirect(False)
            self.iconify()
            self._map_bind = self.bind("<Map>", self._restore_borderless, add="+")
        except tk.TclError:
            pass

    def _restore_borderless(self, _event=None) -> None:
        try:
            self.unbind("<Map>", self._map_bind)
        except tk.TclError:
            pass
        self.after(10, self._apply_borderless)

    def _apply_borderless(self) -> None:
        try:
            self.overrideredirect(True)
            self.lift()
        except tk.TclError:
            pass

    def _set_status(self, text: str) -> None:
        self._status.set(text)

    # musique
    def _music_prepare(self) -> None:
        try:
            self.music.prepare()
        except Exception:  # noqa: BLE001
            self.music.prepare_done = True

    def _sync_music(self) -> None:
        if not self.music.prepare_done:
            return
        if not self._music_synced:
            self._music_synced = True
            if self.music.problem and not self.music.usable:
                self._set_status(f"♪ {self.music.problem}")
            elif self.music.enabled:
                self.music.start()
        elif self.music.enabled and self.music.usable:
            self.music.start()
        self._update_music_button()

    def _update_music_button(self) -> None:
        if self.music.usable and self.music.enabled:
            text, color = "MUSIQUE ON", NEON_GREEN
        elif self.music.usable:
            text, color = "MUSIQUE OFF", RED
        else:
            text, color = "MUSIQUE ?", TXT_DIM
        self._btn_music.configure(text=text, fg=color)

    def toggle_music(self) -> None:
        if not self.music.prepare_done:
            self._set_status("♪ préparation de la chiptune…")
            return
        if not self.music.usable:
            self._set_status(f"♪ {self.music.problem or 'lecteur audio indisponible'}")
            return
        on = self.music.toggle()
        self.config_data["music"] = on
        save_config(self.config_data)
        self._update_music_button()
        self._set_status("♪ musique " + ("activée" if on else "coupée"))

    # boucle de fond
    def _poll(self) -> None:
        self._poll_covers()
        self._sync_music()
        self.after(300, self._poll)

    def _poll_covers(self) -> None:
        changed = False
        while True:
            try:
                key, path = self.covers.results.get_nowait()
            except Empty:
                break
            if path is not None:
                image = self._load_image(path)
                if image is not None:
                    self._thumbs[key] = image
                    changed = True
        if changed:
            self._render_cards()

    def _load_image(self, path: Path) -> tk.PhotoImage | None:
        try:
            image = tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None
        longest = max(image.width(), image.height())
        if longest > COVER_BOX - 2:
            factor = max(1, math.ceil(longest / (COVER_BOX - 2)))
            if factor > 1:
                image = image.subsample(factor)
        return image

    # catalogue
    def refresh_library(self) -> None:
        self._set_status("Chargement du catalogue…")
        site = str(self.config_data.get("site_url") or "")

        def work() -> None:
            data: Any = None
            error: str | None = None
            try:
                data = fetch_library(site)
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
            self.after(0, lambda data=data, error=error: self._on_library(data, error))

        threading.Thread(target=work, daemon=True).start()

    def _on_library(self, data: Any, error: str | None) -> None:
        if error or not isinstance(data, dict):
            self._set_status(f"Site injoignable : {error or 'réponse vide'} (F5 pour réessayer)")
            return
        self.library = data
        self._rebuild_chips()
        self._scroll = 0
        self._selected = None
        self._render_cards()
        total = sum(len(s.get("games") or []) for s in data.get("systems") or [])
        self._set_status(f"{total} jeux — double-clic pour lancer · clic droit = options")

    def _all_games(self) -> list[dict[str, Any]]:
        games: list[dict[str, Any]] = []
        for system in (self.library or {}).get("systems") or []:
            sid = str(system.get("id") or "")
            label = str(system.get("label") or system.get("name") or sid)
            for game in system.get("games") or []:
                item = dict(game)
                item["_system"] = sid
                item["_label"] = label
                games.append(item)
        return games

    def _filtered_games(self) -> list[dict[str, Any]]:
        needle = _norm(self._search.get().strip())
        out: list[dict[str, Any]] = []
        for game in self._all_games():
            if self._filter_system != "all" and game["_system"] != self._filter_system:
                continue
            if needle:
                hay = _norm(f"{game.get('title') or ''} {game.get('file') or ''} {game['_label']}")
                if needle not in hay:
                    continue
            out.append(game)
        return out

    # filtres
    def _on_search(self, _event=None) -> None:
        self._scroll = 0
        self._selected = None
        self._render_cards()

    def _rebuild_chips(self) -> None:
        for child in self._chips.winfo_children():
            child.destroy()
        self._chip_widgets = {}
        systems = [
            (
                str(s.get("id") or ""),
                str(s.get("label") or s.get("name") or s.get("id")),
                len(s.get("games") or []),
            )
            for s in (self.library or {}).get("systems") or []
            if s.get("games")
        ]
        total = sum(count for _sid, _label, count in systems)
        self._add_chip("all", f"TOUTES ({total})")
        for sid, label, count in systems:
            self._add_chip(sid, f"{label.upper()} ({count})")
        self._style_chips()

    def _add_chip(self, sid: str, text: str) -> None:
        lbl = tk.Label(self._chips, text=text, font=self.f_badge, padx=9, pady=4,
                       cursor="hand2", bd=0, highlightthickness=0)
        lbl.bind("<Button-1>", lambda _e, s=sid: self._set_filter(s))
        lbl.bind("<Enter>", lambda _e, s=sid: self._chip_hover(s, True))
        lbl.bind("<Leave>", lambda _e, s=sid: self._chip_hover(s, False))
        lbl.pack(side="left", padx=3, pady=1)
        self._chip_widgets[sid] = lbl

    def _chip_hover(self, sid: str, active: bool) -> None:
        if sid == self._filter_system:
            return
        lbl = self._chip_widgets.get(sid)
        if lbl is not None:
            lbl.configure(bg=BORDER_MID if active else BG_PANEL_HI)

    def _style_chips(self) -> None:
        for sid, lbl in self._chip_widgets.items():
            if sid == self._filter_system:
                lbl.configure(bg=NEON_ORANGE, fg=BG_DARK)
            else:
                lbl.configure(bg=BG_PANEL_HI, fg=TXT)

    def _set_filter(self, sid: str) -> None:
        self._filter_system = sid
        self._style_chips()
        self._scroll = 0
        self._selected = None
        self._render_cards()

    # rendu
    def _on_resize(self, _event=None) -> None:
        size = (self.canvas.winfo_width(), self.canvas.winfo_height())
        if size != self._last_size:
            self._last_size = size
            self._render_cards()

    def _render_cards(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self._cards = []
        self._hover = None
        self._sb = None
        width = max(320, canvas.winfo_width())
        height = max(240, canvas.winfo_height())
        draw_gradient(canvas, 0, 0, width, height)
        draw_scanlines(canvas, 0, 0, width, height)

        games = self._filtered_games()
        if not games:
            canvas.create_text(width // 2, height // 3, text="AUCUN JEU", font=self.f_title_sm,
                               fill=NEON_PINK)
            hint = ("Chargement du catalogue…" if self.library is None
                    else "Essaie un autre filtre ou une autre recherche")
            canvas.create_text(width // 2, height // 3 + 36, text=hint, font=self.f_body,
                               fill=TXT_DIM)
            self._scroll, self._scroll_max = 0, 0
            return

        cols = max(1, min(MAX_COLS, (width - 2 * GRID_PAD + CARD_GAP) // (CARD_W + CARD_GAP)))
        grid_w = cols * CARD_W + (cols - 1) * CARD_GAP
        x0 = max(GRID_PAD, (width - grid_w) // 2)
        y0 = GRID_PAD

        for idx, game in enumerate(games):
            row, col = divmod(idx, cols)
            x = x0 + col * (CARD_W + CARD_GAP)
            y = y0 + row * (CARD_H + CARD_GAP) - self._scroll
            if y + CARD_H < -20 or y > height + 20:
                self._cards.append({"game": game, "x": x, "y": y, "visible": False})
                continue
            self._draw_card(idx, game, x, y)

        rows = (len(games) + cols - 1) // cols
        content_h = y0 + rows * (CARD_H + CARD_GAP) + GRID_PAD
        self._scroll_max = max(0, content_h - height)
        self._scroll = max(0, min(self._scroll, self._scroll_max))
        self._draw_scrollbar(width, height)
        if self._selected is not None and self._selected < len(self._cards):
            self._apply_card_style(self._selected)

    def _draw_card(self, idx: int, game: dict[str, Any], x: int, y: int) -> None:
        canvas = self.canvas
        tags = ("cards", f"card{idx}")
        glow = rounded_rect(canvas, x - 7, y - 7, x + CARD_W + 7, y + CARD_H + 7, 16,
                            fill=NEON_ORANGE, outline="", stipple="gray25", tags=tags, state="hidden")
        panel = rounded_rect(canvas, x, y, x + CARD_W, y + CARD_H, 12,
                             fill=BG_PANEL, outline=BORDER_DIM, width=2, tags=tags)
        accent = canvas.create_rectangle(x + 14, y + 3, x + CARD_W - 14, y + 6,
                                         fill=NEON_PURPLE, outline="", tags=tags)
        canvas.create_text(x + 15, y + 24, text=str(game["_label"]).upper(), anchor="w",
                           font=self.f_badge, fill=NEON_CYAN, tags=tags)
        box_y = y + 36
        thumb, state = self._thumb_for(game)
        if thumb is not None:
            canvas.create_image(x + CARD_W / 2, box_y + COVER_BOX / 2, image=thumb, tags=tags)
        else:
            rounded_rect(canvas, x + 14, box_y, x + CARD_W - 14, box_y + COVER_BOX, 8,
                         fill=BG_DEEP, outline=BORDER_DIM, width=1, tags=tags)
            word = {"pending": "… JAQUETTE …", "none": "PAS DE JAQUETTE"}.get(state, "…")
            canvas.create_text(x + CARD_W / 2, box_y + COVER_BOX / 2, text=word,
                               font=self.f_small, fill=TXT_DARK, tags=tags)
        title = _wrap(game.get("title") or game.get("file") or "?")
        title_id = canvas.create_text(x + CARD_W / 2, y + CARD_H - 44, text=title,
                                      font=self.f_card, fill=TXT, justify="center",
                                      width=CARD_W - 22, tags=tags)
        self._cards.append({
            "game": game, "x": x, "y": y, "visible": True,
            "glow": glow, "panel": panel, "accent": accent, "title": title_id,
        })

    def _thumb_for(self, game: dict[str, Any]) -> tuple[tk.PhotoImage | None, str]:
        key = CoverManager.key(game["_system"], game["file"])
        thumb = self._thumbs.get(key)
        if thumb is not None:
            return thumb, "ready"
        state, path = self.covers.resolve(game["_system"], game["file"],
                                          str(game.get("cover") or ""))
        if state == "ready" and path is not None:
            image = self._load_image(path)
            if image is not None:
                self._thumbs[key] = image
                return image, "ready"
            return None, "none"
        return None, state

    def _draw_scrollbar(self, width: int, height: int) -> None:
        if self._scroll_max <= 0:
            self._sb = None
            return
        canvas = self.canvas
        track_x = width - 12
        thumb_h = max(36, int(height * height / (height + self._scroll_max)))
        thumb_y = int((height - thumb_h) * (self._scroll / self._scroll_max))
        rounded_rect(canvas, track_x, 0, track_x + 6, height, 3, fill="#241140", outline="")
        rounded_rect(canvas, track_x, thumb_y, track_x + 6, thumb_y + thumb_h, 3,
                     fill=NEON_PURPLE, outline="")
        self._sb = (track_x, thumb_y, thumb_h)

    # interactions
    def _card_at(self, ex: int, ey: int) -> int | None:
        for i, card in enumerate(self._cards):
            if not card.get("visible", True):
                continue
            if card["x"] <= ex <= card["x"] + CARD_W and card["y"] <= ey <= card["y"] + CARD_H:
                return i
        return None

    def _apply_card_style(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._cards):
            return
        card = self._cards[idx]
        if not card.get("visible", True):
            return
        canvas = self.canvas
        hovered = idx == self._hover
        selected = idx == self._selected
        if hovered:
            canvas.itemconfigure(card["glow"], state="normal", fill=NEON_ORANGE)
            canvas.itemconfigure(card["panel"], outline=NEON_ORANGE, width=2)
            canvas.itemconfigure(card["title"], fill=NEON_YELLOW)
            canvas.itemconfigure(card["accent"], fill=NEON_ORANGE)
        elif selected:
            canvas.itemconfigure(card["glow"], state="normal", fill=NEON_CYAN, stipple="gray12")
            canvas.itemconfigure(card["panel"], outline=NEON_CYAN, width=3)
            canvas.itemconfigure(card["title"], fill=TXT)
            canvas.itemconfigure(card["accent"], fill=NEON_CYAN)
        else:
            canvas.itemconfigure(card["glow"], state="hidden")
            canvas.itemconfigure(card["panel"], outline=BORDER_DIM, width=2)
            canvas.itemconfigure(card["title"], fill=TXT)
            canvas.itemconfigure(card["accent"], fill=NEON_PURPLE)

    def _set_hover(self, idx: int | None) -> None:
        if idx == self._hover:
            return
        old, self._hover = self._hover, idx
        if old is not None:
            self._apply_card_style(old)
        if idx is not None:
            self._apply_card_style(idx)
        self.canvas.configure(cursor="hand2" if idx is not None else "")

    def _set_selected(self, idx: int | None) -> None:
        old, self._selected = self._selected, idx
        if old is not None:
            self._apply_card_style(old)
        if idx is not None:
            self._apply_card_style(idx)
            if idx < len(self._cards):
                game = self._cards[idx]["game"]
                self._set_status(f"Sélection : {game.get('title') or game.get('file')}")

    def _on_motion(self, event) -> None:
        if self._sb_drag:
            return
        self._set_hover(self._card_at(event.x, event.y))

    def _on_press(self, event) -> None:
        sb = self._sb
        if sb is not None and event.x >= sb[0] - 4:
            if sb[1] <= event.y <= sb[1] + sb[2]:
                self._sb_drag = True
                self._sb_grab = event.y - sb[1]
            else:
                room = max(1, self.canvas.winfo_height() - sb[2])
                self._scroll = int(self._scroll_max * max(0, min(room, event.y - sb[2] / 2)) / room)
                self._render_cards()
            return
        self._set_selected(self._card_at(event.x, event.y))

    def _on_drag(self, event) -> None:
        if not self._sb_drag or self._sb is None:
            return
        _track, _thumb_y, thumb_h = self._sb
        room = max(1, self.canvas.winfo_height() - thumb_h)
        target = max(0, min(room, event.y - self._sb_grab))
        self._scroll = int(self._scroll_max * target / room)
        self._render_cards()

    def _on_double(self, event) -> None:
        idx = self._card_at(event.x, event.y)
        if idx is not None:
            self._set_selected(idx)
            self.play_selected()

    def _on_right(self, event) -> None:
        idx = self._card_at(event.x, event.y)
        if idx is None:
            return
        self._set_selected(idx)
        game = self._cards[idx]["game"]

        def copy_title() -> None:
            self.clipboard_clear()
            self.clipboard_append(str(game.get("title") or game.get("file")))
            self._set_status("Titre copié ✓")

        menu = tk.Menu(self, tearoff=0, bg=BG_PANEL_HI, fg=TXT, activebackground=NEON_ORANGE,
                       activeforeground=BG_DARK, font=self.f_small, bd=0)
        menu.add_command(label="Jouer", command=self.play_selected)
        menu.add_command(label="Jouer en ligne (netplay)", command=self.netplay_selected)
        menu.add_command(label="Sauvegardes…", command=lambda: self._open_saves(game))
        menu.add_separator()
        menu.add_command(label="Copier le titre", command=copy_title)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_wheel(self, event) -> None:
        delta = getattr(event, "delta", 0) or 0
        if delta == 0:
            return
        if abs(delta) >= 120:
            self._scroll_by(int(-delta / 120 * 72))
        else:
            self._scroll_by(int(-delta * 8))

    def _scroll_by(self, dy: int) -> None:
        new = max(0, min(self._scroll + dy, self._scroll_max))
        if new != self._scroll:
            self._scroll = new
            self._render_cards()

    # lancement
    def _selected_game(self) -> dict[str, Any] | None:
        if self._selected is None or self._selected >= len(self._cards):
            return None
        card = self._cards[self._selected]
        return card.get("game")

    def play_selected(self) -> None:
        game = self._selected_game()
        if not game:
            self._set_status("Clique d'abord sur un jeu, puis JOUER !")
            return
        self._start_job(
            lambda progress: launch_game(
                self.config_data, game["_system"], game["file"], progress=progress
            )
        )

    def netplay_selected(self) -> None:
        game = self._selected_game()
        if not game:
            self._set_status("Clique d'abord sur un jeu, puis EN LIGNE !")
            return
        self._open_netplay(game)

    def saves_selected(self) -> None:
        game = self._selected_game()
        if not game:
            self._set_status("Clique d'abord sur un jeu, puis SAUVEGARDES !")
            return
        self._open_saves(game)

    def _start_job(self, job) -> None:
        if self._busy:
            self._set_status("Une partie se prépare déjà…")
            return
        self._busy = True

        def progress(message: str) -> None:
            self.after(0, lambda message=message: self._set_status(str(message)))

        def work() -> None:
            try:
                message = job(progress)
                self.after(0, lambda message=message: self._done(message))
            except LaunchError as exc:
                self.after(0, lambda error=str(exc): self._error(error))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda error=str(exc): self._error(error))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, message: str) -> None:
        self._busy = False
        self._set_status(f"{message} — bonne partie !")

    def _error(self, message: str) -> None:
        self._busy = False
        self._set_status("Oups…")
        self._show_error(message)

    # dialogues
    def _dialog(self, title: str, width: int, height: int) -> tuple[tk.Toplevel, tk.Frame]:
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.configure(bg="#4a1f7a")
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{width}x{height}+{max(0, (sw - width) // 2)}+{max(0, (sh - height) // 2)}")
        outer = tk.Frame(win, bg="#4a1f7a")
        outer.pack(fill="both", expand=True)
        glow2 = tk.Frame(outer, bg="#8a2be2")
        glow2.pack(fill="both", expand=True, padx=2, pady=2)
        glow3 = tk.Frame(glow2, bg=NEON_PINK)
        glow3.pack(fill="both", expand=True, padx=1, pady=1)
        root = tk.Frame(glow3, bg=BG_DARK)
        root.pack(fill="both", expand=True, padx=1, pady=1)
        bar = tk.Frame(root, bg=BG_HEADER, padx=10, pady=6)
        bar.pack(fill="x")
        bar_label = tk.Label(bar, text=title, font=self.f_title_sm, fg=NEON_ORANGE, bg=BG_HEADER)
        bar_label.pack(side="left")
        close = tk.Label(bar, text="X", font=self.f_title_sm, fg=RED, bg=BG_HEADER,
                         padx=8, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: win.destroy())
        origin: list[tuple[int, int]] = []

        def drag_start(event) -> None:
            origin[:] = [(event.x_root - win.winfo_x(), event.y_root - win.winfo_y())]

        def drag_move(event) -> None:
            if origin:
                win.geometry(f"+{event.x_root - origin[0][0]}+{event.y_root - origin[0][1]}")

        for widget in (bar, bar_label):
            widget.bind("<Button-1>", drag_start)
            widget.bind("<B1-Motion>", drag_move)
        body = tk.Frame(root, bg=BG_DARK, padx=16, pady=14)
        body.pack(fill="both", expand=True)
        try:
            win.focus_force()
        except tk.TclError:
            pass
        return win, body

    def _show_error(self, message: str) -> None:
        win, body = self._dialog("ERREUR", 620, 380)
        text = tk.Text(body, bg="#1d0620", fg="#ffb3c8", font=self.f_small, relief="flat",
                       wrap="word", bd=0, highlightthickness=0)
        text.pack(fill="both", expand=True)
        text.insert("1.0", message)
        text.configure(state="disabled")
        neon_label(body, "OK", win.destroy, font=self.f_title_sm, fg=BG_DARK, bg=NEON_PINK,
                   padx=20, pady=8).pack(pady=(10, 0))

    def open_settings(self) -> None:
        win, body = self._dialog("PARAMÈTRES", 760, 560)
        cfg = self.config_data

        def row(label: str, variable: tk.StringVar, browse_title: str) -> None:
            line = tk.Frame(body, bg=BG_DARK)
            line.pack(fill="x", pady=5)
            tk.Label(line, text=label, font=self.f_badge, fg=NEON_CYAN, bg=BG_DARK,
                     width=16, anchor="w").pack(side="left")
            box, _entry = styled_entry(line, variable, font=self.f_body, width=32)
            box.pack(side="left", fill="x", expand=True)
            if browse_title:
                def browse() -> None:
                    from tkinter import filedialog

                    chosen = filedialog.askdirectory(title=browse_title)
                    if chosen:
                        variable.set(chosen)

                neon_label(line, "...", browse, font=self.f_small, fg=TXT, bg=BG_PANEL_HI,
                           hover_bg=BORDER_MID, padx=10, pady=5).pack(side="left", padx=(8, 0))

        site_var = tk.StringVar(value=str(cfg.get("site_url") or ""))
        roms_var = tk.StringVar(value=str(cfg.get("roms_dir") or ""))
        ra_var = tk.StringVar(value=str((cfg.get("retroarch") or {}).get("path") or ""))
        cores_var = tk.StringVar(value=str((cfg.get("retroarch") or {}).get("cores_dir") or ""))
        music_var = tk.StringVar(value=str(cfg.get("music_file") or ""))
        row("Site", site_var, "")
        row("Dossier ROMs", roms_var, "Choisis le dossier des ROMs")
        row("RetroArch", ra_var, "Choisis le dossier de RetroArch")
        row("Dossier cores", cores_var, "Choisis le dossier des cores libretro")
        row("Musique perso", music_var, "Choisis un .wav/.ogg/.mp3 (vide = chiptune)")

        download_var = tk.BooleanVar(value=bool(cfg.get("download_missing_roms", True)))
        tk.Checkbutton(body, text="Télécharger les ROMs manquantes depuis le site",
                       variable=download_var, font=self.f_body, fg=TXT, bg=BG_DARK,
                       activebackground=BG_DARK, activeforeground=NEON_CYAN,
                       selectcolor=BTN_DARK, highlightthickness=0, bd=0).pack(anchor="w", pady=(8, 2))
        tk.Label(body, text="Netplay : pseudo et port se règlent dans le bouton EN LIGNE.",
                 font=self.f_small, fg=TXT_DARK, bg=BG_DARK).pack(anchor="w")

        def save() -> None:
            cfg["site_url"] = site_var.get().strip() or "https://retro.kirbytrim.buzz"
            cfg["roms_dir"] = roms_var.get().strip()
            cfg["download_missing_roms"] = bool(download_var.get())
            cfg["music_file"] = music_var.get().strip()
            cfg.setdefault("retroarch", {})
            cfg["retroarch"]["path"] = ra_var.get().strip()
            cfg["retroarch"]["cores_dir"] = cores_var.get().strip()
            save_config(cfg)
            self.covers.update_config(cfg["site_url"], cfg["roms_dir"])
            try:
                self._music_synced = False
                self.music.stop()
                self.music.prepare()
                self.music.prepare_done = True
                self._sync_music()
            except Exception:  # noqa: BLE001
                pass
            win.destroy()
            self._set_status("Paramètres enregistrés ✓")
            self.refresh_library()

        def protocol() -> None:
            try:
                message = install_protocol()
                self._set_status(message if isinstance(message, str) else "Protocole installé ✓")
            except Exception as exc:  # noqa: BLE001
                self._show_error(f"Protocole kirbyretro:// : {exc}")

        buttons = tk.Frame(body, bg=BG_DARK)
        buttons.pack(fill="x", side="bottom", pady=(12, 0))
        neon_label(buttons, "DIAGNOSTIC", self.open_doctor, font=self.f_badge, fg=TXT,
                   bg=BG_PANEL_HI, hover_bg=BORDER_MID, padx=14, pady=8).pack(side="left")
        neon_label(buttons, "ASSOCIER kirbyretro://", protocol, font=self.f_badge, fg=TXT,
                   bg=BG_PANEL_HI, hover_bg=BORDER_MID, padx=14, pady=8).pack(side="left", padx=8)
        neon_label(buttons, "ENREGISTRER", save, font=self.f_title_sm, fg=BG_DARK, bg=NEON_GREEN,
                   hover_bg=NEON_YELLOW, padx=16, pady=8).pack(side="right")
        neon_label(buttons, "ANNULER", win.destroy, font=self.f_badge, fg=TXT_DIM,
                   bg=BG_PANEL_HI, hover_bg=BORDER_MID, padx=14, pady=8).pack(side="right", padx=8)

    def open_doctor(self) -> None:
        win, body = self._dialog("DIAGNOSTIC", 900, 580)
        text = tk.Text(body, bg="#0d0518", fg=NEON_GREEN, font=self.f_small, relief="flat",
                       wrap="word", bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(body, command=text.yview, width=10)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("1.0", "Collecte du diagnostic… (quelques secondes)")
        text.configure(state="disabled")

        def work() -> None:
            from .doctor import collect

            try:
                report = collect()
            except Exception as exc:  # noqa: BLE001
                report = f"Échec du diagnostic : {exc}"

            def show() -> None:
                text.configure(state="normal")
                text.delete("1.0", "end")
                text.insert("1.0", report)
                text.configure(state="disabled")

            self.after(0, show)

        threading.Thread(target=work, daemon=True).start()

    def _open_netplay(self, game: dict[str, Any]) -> None:
        title = str(game.get("title") or game.get("file") or "?")
        win, body = self._dialog(f"EN LIGNE — {title}", 680, 620)
        win.lift()
        cfg = self.config_data.setdefault("netplay", {})

        tk.Label(body, text=f"{game.get('_label') or game.get('_system')} · netplay RetroArch",
                 font=self.f_small, fg=TXT_DIM, bg=BG_DARK).pack(anchor="w")

        top = tk.Frame(body, bg=BG_DARK)
        top.pack(fill="x", pady=(8, 4))
        tk.Label(top, text="Pseudo", font=self.f_badge, fg=NEON_CYAN, bg=BG_DARK).pack(side="left")
        nick_var = tk.StringVar(value=str(cfg.get("nickname") or "Kirby"))
        nick_box, _ne = styled_entry(top, nick_var, font=self.f_body, width=14)
        nick_box.pack(side="left", padx=8)
        tk.Label(top, text="Port", font=self.f_badge, fg=NEON_CYAN, bg=BG_DARK).pack(side="left",
                                                                                      padx=(14, 0))
        port_var = tk.StringVar(value=str(cfg.get("port") or DEFAULT_PORT))
        port_box, _pe = styled_entry(top, port_var, font=self.f_body, width=6)
        port_box.pack(side="left", padx=8)

        mode = tk.StringVar(value="host")
        relay_var = tk.BooleanVar(value=bool(cfg.get("use_relay", False)))
        address_var = tk.StringVar(value=str(cfg.get("last_host") or ""))
        password_var = tk.StringVar()

        host_frame = tk.Frame(body, bg=BG_DARK)
        join_frame = tk.Frame(body, bg=BG_DARK)
        pass_frame = tk.Frame(body, bg=BG_DARK)

        def swap() -> None:
            host_frame.pack_forget()
            join_frame.pack_forget()
            pass_frame.pack_forget()
            if mode.get() == "host":
                host_frame.pack(fill="x", pady=4)
                pass_frame.pack(fill="x")
            else:
                join_frame.pack(fill="x", pady=4)

        modes = tk.Frame(body, bg=BG_DARK)
        modes.pack(fill="x", pady=(8, 2))
        for value, label in (("host", "HÉBERGER"), ("join", "REJOINDRE")):
            tk.Radiobutton(modes, text=label, value=value, variable=mode, command=swap,
                           font=self.f_body, fg=TXT, bg=BG_DARK, activebackground=BG_DARK,
                           activeforeground=NEON_CYAN, selectcolor=BTN_DARK,
                           highlightthickness=0, bd=0).pack(side="left", padx=(0, 18))

        addresses = candidate_addresses()
        values = [f"{tag} — {ip}" for tag, ip in addresses] or ["(aucune adresse détectée)"]

        tk.Label(host_frame, text="Adresse à donner à ton ami :", font=self.f_badge,
                 fg=NEON_CYAN, bg=BG_DARK).pack(anchor="w", pady=(8, 2))
        line = tk.Frame(host_frame, bg=BG_DARK)
        line.pack(fill="x")
        combo = ttk.Combobox(line, values=values, width=32, state="readonly", font=self.f_small)
        combo.current(0)
        combo.pack(side="left")

        def copy_address() -> None:
            if not addresses:
                return
            index = min(max(combo.current(), 0), len(addresses) - 1)
            self.clipboard_clear()
            self.clipboard_append(f"{addresses[index][1]}:{port_var.get().strip() or DEFAULT_PORT}")
            self._set_status("Adresse copiée ✓ — colle-la à ton ami")

        neon_label(line, "COPIER", copy_address, font=self.f_badge, fg=BG_DARK, bg=NEON_CYAN,
                   hover_bg=NEON_YELLOW, padx=12, pady=6).pack(side="left", padx=8)
        tk.Checkbutton(host_frame,
                       text="Relais RetroArch (aucun port à ouvrir — l'ami rejoint via le menu Netplay)",
                       variable=relay_var, font=self.f_small, fg=TXT, bg=BG_DARK,
                       activebackground=BG_DARK, activeforeground=NEON_CYAN,
                       selectcolor=BTN_DARK, highlightthickness=0, bd=0).pack(anchor="w", pady=(8, 2))
        tk.Label(host_frame,
                 text="Sans relais : ton ami doit être sur ton Tailscale ou ton réseau local "
                      "(sinon ouvre le port UDP sur ta box). Windows : accepte le pare-feu.",
                 font=self.f_small, fg=TXT_DARK, bg=BG_DARK, wraplength=580,
                 justify="left").pack(anchor="w")

        tk.Label(pass_frame, text="Mot de passe (optionnel, pour héberger)", font=self.f_badge,
                 fg=NEON_CYAN, bg=BG_DARK).pack(anchor="w", pady=(8, 2))
        pass_box, _pw = styled_entry(pass_frame, password_var, font=self.f_body, width=22)
        pass_box.pack(anchor="w")

        tk.Label(join_frame, text="Adresse donnée par ton ami :", font=self.f_badge,
                 fg=NEON_CYAN, bg=BG_DARK).pack(anchor="w", pady=(8, 2))
        join_box, _je = styled_entry(join_frame, address_var, font=self.f_body, width=32)
        join_box.pack(anchor="w")
        tk.Label(join_frame,
                 text="Il clique HÉBERGER puis COPIER et t'envoie l'adresse.\n"
                      "S'il utilise le relais : RetroArch → Netplay → actualise → rejoins son pseudo.",
                 font=self.f_small, fg=TXT_DARK, bg=BG_DARK, justify="left").pack(anchor="w",
                                                                                   pady=(4, 0))

        def start() -> None:
            is_host = mode.get() == "host"
            try:
                port = int((port_var.get() or "").strip() or DEFAULT_PORT)
                if not 1 <= port <= 65535:
                    raise ValueError
            except ValueError:
                self._show_error("Port invalide (1 – 65535).")
                return
            address = address_var.get().strip()
            if not is_host and not address:
                self._show_error("Indique l'adresse de la partie (donnée par l'hôte).")
                return
            nickname = nick_var.get().strip() or "Kirby"
            use_relay = bool(relay_var.get()) and is_host
            password = password_var.get().strip() if is_host else ""
            cfg.update({"nickname": nickname, "port": port, "use_relay": use_relay,
                        "last_host": address})
            save_config(self.config_data)
            win.destroy()
            self._start_job(
                lambda progress: launch_netplay(
                    self.config_data, game["_system"], game["file"], host=is_host,
                    address=address, port=port, nickname=nickname, password=password,
                    use_relay=use_relay, progress=progress,
                )
            )

        buttons = tk.Frame(body, bg=BG_DARK)
        buttons.pack(fill="x", side="bottom", pady=(12, 4))
        neon_label(buttons, "LANCER EN LIGNE", start, font=self.f_title_sm, fg=BG_DARK,
                   bg=NEON_PURPLE, hover_fg=TXT, hover_bg=NEON_PINK, padx=16, pady=8).pack(side="right")
        neon_label(buttons, "ANNULER", win.destroy, font=self.f_badge, fg=TXT_DIM,
                   bg=BG_PANEL_HI, hover_bg=BORDER_MID, padx=14, pady=8).pack(side="right", padx=8)
        tk.Label(body,
                 text="Netplay : idéal NES / SNES / Mega Drive / GBA / PSX · variable N64 · "
                      "pas dispo DS / Wii / PSP.\nMême jeu et même core chez les deux — "
                      "les ROMs se téléchargent toutes seules.",
                 font=self.f_small, fg=TXT_DARK, bg=BG_DARK, justify="left").pack(anchor="w",
                                                                                 pady=(6, 0))

    # sauvegardes
    def _open_saves(self, game: dict[str, Any]) -> None:
        title = str(game.get("title") or game.get("file") or "?")
        system = game["_system"]
        roms_dir = str(self.config_data.get("roms_dir") or "") or None
        win, body = self._dialog(f"SAUVEGARDES — {title}", 880, 620)

        native = find_native(system)
        native_name = Path(native).name if native else ""
        target_dir, why = saves_mod.retroarch_save_dir()

        tk.Label(body, text=f"Cible RetroArch : {target_dir if target_dir else '—'}",
                 font=self.f_small, fg=NEON_CYAN if target_dir else RED, bg=BG_DARK,
                 anchor="w", wraplength=820, justify="left").pack(fill="x")
        tk.Label(body, text=why, font=self.f_small, fg=TXT_DARK, bg=BG_DARK,
                 anchor="w", wraplength=820, justify="left").pack(fill="x")
        if native_name:
            tk.Label(body, text=f"Émulateur natif détecté : {native_name}", font=self.f_small,
                     fg=TXT_DIM, bg=BG_DARK, anchor="w").pack(fill="x")

        list_wrap = tk.Frame(body, bg=BG_DARK)
        list_wrap.pack(fill="both", expand=True, pady=(10, 6))
        listbox = tk.Listbox(list_wrap, font=self.f_small, bg=BTN_DARK, fg=TXT,
                             selectbackground=NEON_ORANGE, selectforeground=BG_DARK,
                             relief="flat", bd=0, highlightthickness=1,
                             highlightbackground=BORDER_MID, activestyle="none",
                             selectmode=tk.EXTENDED)
        scroll = tk.Scrollbar(list_wrap, command=listbox.yview, width=10)
        listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        listbox.pack(fill="both", expand=True)

        note = tk.Label(body, text="", font=self.f_small, fg=TXT_DIM, bg=BG_DARK,
                        anchor="w", wraplength=820, justify="left")
        note.pack(fill="x", pady=(0, 6))

        state: dict[str, list[saves_mod.SaveFile]] = {"files": []}

        def show(message: str, color: str = TXT_DIM) -> None:
            note.configure(text=message, fg=color)

        def refresh() -> None:
            listbox.delete(0, "end")
            state["files"] = saves_mod.find_saves(system, game["file"], roms_dir)
            home = str(Path.home())
            for save in state["files"]:
                shown = str(save.path).replace(home, "~", 1)
                listbox.insert(
                    "end",
                    f"  {save.source} — {shown}  ({save.size_ko()} Ko, {save.date()})",
                )
            if not state["files"]:
                listbox.insert("end", "  Aucune sauvegarde trouvée pour ce jeu.")
            else:
                listbox.selection_set(0)

        def selected() -> list[saves_mod.SaveFile]:
            return [state["files"][i] for i in listbox.curselection() if i < len(state["files"])]

        def do_retroarch() -> None:
            files = selected()
            if not files:
                show("Sélectionne d'abord une sauvegarde dans la liste.", RED)
                return
            try:
                show(saves_mod.import_to_retroarch(system, game["file"], files), NEON_GREEN)
            except saves_mod.SaveError as exc:
                show(str(exc), RED)
            except Exception as exc:  # noqa: BLE001
                show(f"Échec de la copie : {exc}", RED)
            refresh()

        def do_native() -> None:
            files = selected()
            if not files:
                show("Sélectionne d'abord une sauvegarde dans la liste.", RED)
                return
            try:
                show(saves_mod.import_to_native(system, game["file"], files[0], roms_dir),
                     NEON_GREEN)
            except saves_mod.SaveError as exc:
                show(str(exc), RED)
            except Exception as exc:  # noqa: BLE001
                show(f"Échec de la copie : {exc}", RED)

        def do_export() -> None:
            files = selected()
            if not files:
                show("Sélectionne d'abord une sauvegarde dans la liste.", RED)
                return
            from tkinter import filedialog

            dest = filedialog.asksaveasfilename(
                title="Exporter une copie de la sauvegarde",
                initialfile=files[0].path.name,
            )
            if not dest:
                return
            try:
                path = saves_mod.export_copy(files[0], Path(dest))
                show(f"Copie exportée vers {path}", NEON_GREEN)
            except Exception as exc:  # noqa: BLE001
                show(f"Échec de l'export : {exc}", RED)

        def do_choose() -> None:
            from tkinter import filedialog

            chosen = filedialog.askopenfilename(
                title="Choisir un fichier de sauvegarde (export du navigateur, autre émulateur…)",
            )
            if not chosen:
                return
            state["files"].insert(0, saves_mod.SaveFile.from_path(Path(chosen), system))
            listbox.insert(0, f"  choisi — {chosen}")
            listbox.selection_clear(0, "end")
            listbox.selection_set(0)
            show("Fichier ajouté en tête de liste : tu peux l'importer vers RetroArch.")

        row = tk.Frame(body, bg=BG_DARK)
        row.pack(fill="x")
        neon_label(row, "IMPORTER VERS RETROARCH", do_retroarch, font=self.f_badge,
                   fg=BG_DARK, bg=NEON_ORANGE, hover_bg=NEON_YELLOW, padx=14, pady=8).pack(side="left")
        if native_name:
            neon_label(row, f"VERS {native_name.upper()}", do_native, font=self.f_badge,
                       fg=TXT, bg=NEON_PURPLE, hover_fg=BG_DARK, hover_bg=NEON_PINK,
                       padx=14, pady=8).pack(side="left", padx=8)
        neon_label(row, "EXPORTER UNE COPIE", do_export, font=self.f_badge, fg=TXT,
                   bg=BG_PANEL_HI, hover_bg=BORDER_MID, padx=12, pady=8).pack(side="left", padx=8)
        neon_label(row, "CHOISIR UN FICHIER…", do_choose, font=self.f_badge, fg=TXT,
                   bg=BG_PANEL_HI, hover_bg=BORDER_MID, padx=12, pady=8).pack(side="left")
        neon_label(row, "ACTUALISER", refresh, font=self.f_badge, fg=TXT_DIM,
                   bg=BG_PANEL_HI, hover_bg=BORDER_MID, padx=12, pady=8).pack(side="right")

        tk.Label(body,
                 text="Seules les sauvegardes de jeu se transfèrent entre émulateurs, pas les états "
                      "(savestates). Chaque copie garde l'ancienne version en .bak.",
                 font=self.f_small, fg=TXT_DARK, bg=BG_DARK, anchor="w",
                 wraplength=820, justify="left").pack(fill="x", pady=(8, 0))
        refresh()

    # fermeture
    def on_close(self) -> None:
        try:
            self.music.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass


def run_gui() -> None:
    from .theme import ensure_fonts, resolve_fonts

    ensure_fonts()
    probe = tk.Tk()
    title_family, body_family = resolve_fonts(probe)
    probe.destroy()
    app = LauncherApp(title_family=title_family, body_family=body_family)
    app.mainloop()


main = run_gui
