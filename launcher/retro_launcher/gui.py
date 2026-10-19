"""Interface Tkinter du launcher : liste de jeux, RetroArch, netplay, sauvegardes."""
from __future__ import annotations

import math
import threading
import tkinter as tk
import unicodedata
from pathlib import Path
from queue import Empty
from tkinter import filedialog, ttk
from typing import Any

from . import __version__
from . import saves as saves_mod
from .api import fetch_library
from .config import load_config, save_config
from .covers import CoverManager
from .detect import autofill, find_native, flatpak_native
from .launch import LaunchError, launch_game, launch_netplay, local_rom_path
from .netplay import DEFAULT_PORT, candidate_addresses
from .protocol import install_protocol

# Palette sombre, sobre.
BG = "#2d2d30"
PANEL = "#383838"
FIELD = "#262626"
LINE = "#4a4a4c"
FG = "#e9e9e9"
DIM = "#9d9d9d"
SEL = "#2f6ea5"
DANGER = "#e06c75"
OK = "#8cc265"

THUMB_H = 46
ROW_H = 56


def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(text).lower()) if not unicodedata.combining(c)
    )


def _human_size(game: dict[str, Any]) -> str:
    try:
        size = int(game.get("size") or 0)
    except (TypeError, ValueError):
        return ""
    if size <= 0:
        return ""
    mo = size / (1024 * 1024)
    if mo >= 1024:
        return f"{mo / 1024:.2f} Gio"
    if mo >= 1:
        return f"{mo:.1f} Mio"
    return f"{max(1, size // 1024)} Kio"


class LauncherApp(tk.Tk):
    def __init__(self, title_family: str = "", body_family: str = "") -> None:
        super().__init__()
        self.title(f"Kirby Retro Launcher v{__version__}")
        self.configure(bg=BG)
        self.minsize(920, 560)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(1180, max(920, sw - 120)), min(760, max(560, sh - 120))
        self.geometry(
            f"{width}x{height}+{max(0, (sw - width) // 2)}+{max(0, (sh - height) // 2 - 20)}"
        )

        self.config_data = autofill(load_config())
        self.library: dict[str, Any] | None = None
        self.covers = CoverManager(
            str(self.config_data.get("site_url") or ""),
            str(self.config_data.get("roms_dir") or ""),
        )

        self._rows: dict[str, dict[str, Any]] = {}
        self._thumbs: dict[str, tk.PhotoImage] = {}
        self._filter_map: dict[str, str] = {"Toutes les consoles": "all"}
        self._filter_system = "all"
        self._sort_col = "title"
        self._sort_rev = False
        self._busy = False

        self._status = tk.StringVar(value="Chargement du catalogue…")
        self._count = tk.StringVar(value="")
        self._search = tk.StringVar()

        self._setup_style()
        self._build_menu()
        self._build_toolbar()
        self._build_list()
        self._build_statusbar()

        self.after(150, self.refresh_library)
        self.after(300, self._poll)
        self.bind("<F5>", lambda _e: self.refresh_library())
        self.bind("<Control-q>", lambda _e: self.on_close())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # apparence
    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=FG, fieldbackground=FIELD,
                        bordercolor=LINE, lightcolor=PANEL, darkcolor=PANEL, focuscolor=BG)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Dim.TLabel", foreground=DIM)
        style.configure("TButton", background=PANEL, foreground=FG, relief="flat",
                        padding=(10, 5), borderwidth=1)
        style.map("TButton",
                  background=[("pressed", "#4c4c50"), ("active", "#454549"), ("disabled", BG)],
                  foreground=[("disabled", DIM)])
        style.configure("Tool.TButton", padding=(12, 6))
        style.configure("TCheckbutton", background=BG, foreground=FG, focuscolor=BG)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TRadiobutton", background=BG, foreground=FG, focuscolor=BG)
        style.map("TRadiobutton", background=[("active", BG)])
        style.configure("TEntry", fieldbackground=FIELD, foreground=FG, insertcolor=FG,
                        bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure("TSeparator", background=LINE)
        style.configure("TProgressbar", background=SEL, troughcolor=FIELD, bordercolor=BG,
                        lightcolor=SEL, darkcolor=SEL)
        style.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG,
                        bordercolor=LINE, lightcolor=FIELD, darkcolor=FIELD, relief="flat",
                        rowheight=ROW_H)
        style.map("Treeview",
                  background=[("selected", SEL)], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=PANEL, foreground=FG, relief="flat",
                        padding=(6, 4))
        style.map("Treeview.Heading", background=[("active", "#454549")])
        style.configure("TCombobox", fieldbackground=FIELD, background=PANEL, foreground=FG,
                        arrowcolor=FG, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.map("TCombobox",
                  fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)],
                  background=[("readonly", PANEL)])
        # listes déroulantes et menus (options classiques Tk)
        self.option_add("*TCombobox*Listbox.background", FIELD)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", SEL)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*Menu.background", PANEL)
        self.option_add("*Menu.foreground", FG)
        self.option_add("*Menu.activeBackground", SEL)
        self.option_add("*Menu.activeForeground", "#ffffff")
        self.option_add("*Menu.activeBorderWidth", 0)
        self.option_add("*Menu.borderWidth", 1)
        self.option_add("*Menu.relief", "flat")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        fichier = tk.Menu(menubar, tearoff=0)
        fichier.add_command(label="Lancer le jeu sélectionné", command=self.play_selected)
        fichier.add_command(label="Actualiser la bibliothèque", command=self.refresh_library)
        fichier.add_separator()
        fichier.add_command(label="Quitter", command=self.on_close)
        menubar.add_cascade(label="Fichier", menu=fichier)

        emulation = tk.Menu(menubar, tearoff=0)
        emulation.add_command(label="Démarrer", command=self.play_selected)
        emulation.add_command(label="Jouer en ligne (netplay)…", command=self.netplay_selected)
        emulation.add_command(label="Sauvegardes…", command=self.saves_selected)
        menubar.add_cascade(label="Émulation", menu=emulation)

        options = tk.Menu(menubar, tearoff=0)
        options.add_command(label="Paramètres…", command=self.open_settings)
        options.add_separator()
        options.add_command(label="Installer le protocole kirbyretro://", command=self._install_protocol)
        options.add_command(label="Diagnostic…", command=self.open_doctor)
        menubar.add_cascade(label="Options", menu=options)

        self._view_menu = tk.Menu(menubar, tearoff=0)
        self._view_menu.add_command(label="Toutes les consoles",
                                    command=lambda: self._set_filter("all"))
        menubar.add_cascade(label="Affichage", menu=self._view_menu)

        aide = tk.Menu(menubar, tearoff=0)
        aide.add_command(label="À propos", command=self._about)
        menubar.add_cascade(label="Aide", menu=aide)

        self.config(menu=menubar)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Button(bar, text="Démarrer", style="Tool.TButton",
                   command=self.play_selected).pack(side="left")
        ttk.Button(bar, text="En ligne", style="Tool.TButton",
                   command=self.netplay_selected).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Sauvegardes", style="Tool.TButton",
                   command=self.saves_selected).pack(side="left", padx=(6, 0))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10, pady=2)
        ttk.Button(bar, text="Rafraîchir", style="Tool.TButton",
                   command=self.refresh_library).pack(side="left")
        ttk.Button(bar, text="Paramètres", style="Tool.TButton",
                   command=self.open_settings).pack(side="left", padx=(6, 0))

        ttk.Label(bar, text="Rechercher :", style="Dim.TLabel").pack(side="left", padx=(18, 4))
        search = ttk.Entry(bar, textvariable=self._search, width=24)
        search.pack(side="left")
        search.bind("<KeyRelease>", self._on_search)

        ttk.Label(bar, text="Console :", style="Dim.TLabel").pack(side="left", padx=(14, 4))
        self._filter_box = ttk.Combobox(bar, state="readonly", width=20,
                                        values=["Toutes les consoles"])
        self._filter_box.current(0)
        self._filter_box.pack(side="left")
        self._filter_box.bind("<<ComboboxSelected>>", self._on_filter_combo)

    def _build_list(self) -> None:
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=10, pady=(4, 0))
        columns = ("title", "console", "year", "size", "file")
        self.tree = ttk.Treeview(wrap, columns=columns, show="tree headings",
                                 selectmode="browse", height=6)
        self.tree.heading("#0", text="Bannière")
        self.tree.column("#0", width=76, minwidth=76, stretch=False, anchor="center")
        headings = (
            ("title", "Titre", 420, "w"),
            ("console", "Console", 130, "w"),
            ("year", "Année", 70, "center"),
            ("size", "Taille", 90, "e"),
            ("file", "Fichier", 260, "w"),
        )
        for key, text, width, anchor in headings:
            self.tree.heading(key, text=text, command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=key in ("title", "file"))
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", lambda _e: self.play_selected())
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(6, 8))
        ttk.Label(bar, textvariable=self._status, style="Dim.TLabel").pack(side="left")
        self._progress = ttk.Progressbar(bar, mode="indeterminate", length=140)
        ttk.Label(bar, textvariable=self._count, style="Dim.TLabel").pack(side="right")

    def _set_status(self, text: str) -> None:
        self._status.set(text)

    # boucle de fond
    def _poll(self) -> None:
        self._poll_covers()
        self.after(300, self._poll)

    def _poll_covers(self) -> None:
        while True:
            try:
                key, path = self.covers.results.get_nowait()
            except Empty:
                break
            if path is None:
                continue
            image = self._load_thumb(path)
            if image is None:
                continue
            self._thumbs[key] = image
            for iid, game in self._rows.items():
                if CoverManager.key(game["_system"], game["file"]) == key:
                    self.tree.item(iid, image=image)

    def _load_thumb(self, path: Path) -> tk.PhotoImage | None:
        try:
            image = tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None
        factor = math.ceil(image.height() / THUMB_H)
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
            self.after(0, lambda: self._on_library(data, error))

        threading.Thread(target=work, daemon=True).start()

    def _on_library(self, data: Any, error: str | None) -> None:
        if error or not isinstance(data, dict):
            self._set_status(f"Site injoignable : {error or 'réponse vide'} (F5 pour réessayer)")
            return
        self.library = data
        self._rebuild_filter_choices()
        self._render_list()
        total = sum(len(s.get("games") or []) for s in data.get("systems") or [])
        self._set_status(f"{total} jeux — double-clic pour lancer")

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
        games: list[dict[str, Any]] = []
        for game in self._all_games():
            if self._filter_system != "all" and game["_system"] != self._filter_system:
                continue
            if needle:
                hay = _norm(f"{game.get('title') or ''} {game.get('file') or ''} {game['_label']}")
                if needle not in hay:
                    continue
            games.append(game)
        keys = {
            "title": lambda g: _norm(g.get("title") or g.get("file") or ""),
            "console": lambda g: _norm(g.get("_label") or ""),
            "year": lambda g: int(g.get("year") or 0),
            "size": lambda g: int(g.get("size") or 0),
            "file": lambda g: _norm(g.get("file") or ""),
        }
        games.sort(key=keys.get(self._sort_col, keys["title"]), reverse=self._sort_rev)
        return games

    # liste
    def _render_list(self) -> None:
        selected = self._selected_game()
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        games = self._filtered_games()
        for idx, game in enumerate(games):
            iid = f"g{idx}"
            self._rows[iid] = game
            self.tree.insert(
                "", "end", iid=iid, text="",
                values=(
                    game.get("title") or game.get("file") or "?",
                    game.get("_label") or game.get("_system") or "",
                    game.get("year") or "",
                    _human_size(game),
                    game.get("file") or "",
                ),
            )
            self._apply_thumb(iid, game)
        if selected is not None:
            for iid, game in self._rows.items():
                if game is selected:
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
                    break
        count = len(games)
        self._count.set(f"{count} jeu" + ("x" if count != 1 else ""))
        if count == 0 and self.library is not None:
            self._set_status("Aucun jeu — change de filtre ou vérifie le dossier ROMs")

    def _apply_thumb(self, iid: str, game: dict[str, Any]) -> None:
        key = CoverManager.key(game["_system"], game["file"])
        thumb = self._thumbs.get(key)
        if thumb is None:
            state, path = self.covers.resolve(game["_system"], game["file"],
                                              str(game.get("cover") or ""))
            if state == "ready" and path is not None:
                thumb = self._load_thumb(path)
                if thumb is not None:
                    self._thumbs[key] = thumb
        if thumb is not None and self.tree.exists(iid):
            self.tree.item(iid, image=thumb)

    def _sort_by(self, column: str) -> None:
        if self._sort_col == column:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col, self._sort_rev = column, False
        self._render_list()

    def _selected_game(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if selection:
            return self._rows.get(selection[0])
        return None

    def _on_select(self, _event=None) -> None:
        game = self._selected_game()
        if game:
            self._set_status(f"Sélection : {game.get('title') or game.get('file')}")

    def _on_double_click(self, event) -> None:
        if self.tree.identify_row(event.y):
            self.play_selected()

    def _on_right_click(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        game = self._rows.get(iid)
        if not game:
            return

        def copy_title() -> None:
            self.clipboard_clear()
            self.clipboard_append(str(game.get("title") or game.get("file")))
            self._set_status("Titre copié")

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Démarrer", command=self.play_selected)
        menu.add_command(label="Jouer en ligne (netplay)…", command=self.netplay_selected)
        menu.add_command(label="Sauvegardes…", command=lambda: self._open_saves(game))
        menu.add_separator()
        menu.add_command(label="Copier le titre", command=copy_title)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # filtres
    def _on_search(self, _event=None) -> None:
        self._render_list()

    def _rebuild_filter_choices(self) -> None:
        self._filter_map = {"Toutes les consoles": "all"}
        labels = ["Toutes les consoles"]
        for system in (self.library or {}).get("systems") or []:
            if not system.get("games"):
                continue
            sid = str(system.get("id") or "")
            label = str(system.get("label") or system.get("name") or sid)
            text = f"{label} ({len(system.get('games') or [])})"
            self._filter_map[text] = sid
            labels.append(text)
        self._filter_box.configure(values=labels)
        self._filter_box.set("Toutes les consoles")
        self._view_menu.delete(0, "end")
        for text in labels:
            self._view_menu.add_command(
                label=text, command=lambda t=text: self._set_filter(self._filter_map[t])
            )

    def _on_filter_combo(self, _event=None) -> None:
        self._set_filter(self._filter_map.get(self._filter_box.get(), "all"))

    def _set_filter(self, sid: str) -> None:
        self._filter_system = sid
        for text, value in self._filter_map.items():
            if value == sid:
                self._filter_box.set(text)
                break
        self._render_list()

    # lancement
    def play_selected(self) -> None:
        game = self._selected_game()
        if not game:
            self._set_status("Sélectionne un jeu dans la liste, puis Démarrer")
            return
        self._start_job(
            lambda progress: launch_game(
                self.config_data, game["_system"], game["file"], progress=progress
            )
        )

    def netplay_selected(self) -> None:
        game = self._selected_game()
        if not game:
            self._set_status("Sélectionne un jeu dans la liste, puis En ligne")
            return
        self._open_netplay(game)

    def saves_selected(self) -> None:
        game = self._selected_game()
        if not game:
            self._set_status("Sélectionne un jeu dans la liste, puis Sauvegardes")
            return
        self._open_saves(game)

    def _start_job(self, job) -> None:
        if self._busy:
            self._set_status("Une partie se prépare déjà…")
            return
        self._busy = True
        self._progress.pack(side="right", padx=(0, 10))
        self._progress.start(12)

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

    def _stop_progress(self) -> None:
        self._progress.stop()
        self._progress.pack_forget()

    def _done(self, message: str) -> None:
        self._busy = False
        self._stop_progress()
        self._set_status(f"{message} — bonne partie !")

    def _error(self, message: str) -> None:
        self._busy = False
        self._stop_progress()
        self._set_status("Échec du lancement")
        self._show_error(message)

    # dialogues
    def _dialog(self, title: str, width: int, height: int) -> tuple[tk.Toplevel, ttk.Frame]:
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=BG)
        win.transient(self)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{width}x{height}+{max(0, (sw - width) // 2)}+{max(0, (sh - height) // 2)}")
        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)
        win.bind("<Escape>", lambda _e: win.destroy())
        return win, body

    def _show_error(self, message: str) -> None:
        win, body = self._dialog("Erreur", 640, 320)
        text = tk.Text(body, wrap="word", relief="flat", bd=0, highlightthickness=1,
                       highlightbackground=LINE, bg=FIELD, fg=FG, font="TkDefaultFont")
        text.pack(fill="both", expand=True)
        text.insert("1.0", message)
        text.configure(state="disabled")
        ttk.Button(body, text="Fermer", command=win.destroy).pack(side="right", pady=(10, 0))

    def open_settings(self) -> None:
        win, body = self._dialog("Paramètres", 780, 520)
        cfg = self.config_data
        body.columnconfigure(1, weight=1)

        site_var = tk.StringVar(value=str(cfg.get("site_url") or ""))
        roms_var = tk.StringVar(value=str(cfg.get("roms_dir") or ""))
        ra_var = tk.StringVar(value=str((cfg.get("retroarch") or {}).get("path") or ""))
        cores_var = tk.StringVar(value=str((cfg.get("retroarch") or {}).get("cores_dir") or ""))

        def browse_row(row: int, label: str, variable: tk.StringVar, title: str) -> None:
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(body, textvariable=variable).grid(row=row, column=1, sticky="ew",
                                                        padx=(8, 8), pady=5)
            if title:
                def browse() -> None:
                    chosen = filedialog.askdirectory(title=title)
                    if chosen:
                        variable.set(chosen)

                ttk.Button(body, text="Parcourir…", command=browse).grid(row=row, column=2, pady=5)

        browse_row(0, "Site", site_var, "")
        browse_row(1, "Dossier ROMs", roms_var, "Choisis le dossier des ROMs")
        browse_row(2, "RetroArch", ra_var, "Choisis le dossier de RetroArch")
        browse_row(3, "Dossier cores", cores_var, "Choisis le dossier des cores libretro")

        download_var = tk.BooleanVar(value=bool(cfg.get("download_missing_roms", True)))
        ttk.Checkbutton(body, text="Télécharger les ROMs manquantes depuis le site",
                        variable=download_var).grid(row=4, column=0, columnspan=3,
                                                    sticky="w", pady=(10, 2))
        auto_var = tk.BooleanVar(value=bool(cfg.get("auto_sync_saves", True)))
        ttk.Checkbutton(body,
                        text="Importer automatiquement les sauvegardes des émulateurs natifs au lancement",
                        variable=auto_var).grid(row=5, column=0, columnspan=3,
                                                sticky="w", pady=(2, 2))
        sysfiles_var = tk.BooleanVar(value=bool(cfg.get("install_dolphin_sysfiles", True)))
        ttk.Checkbutton(body,
                        text="Installer les fichiers système Dolphin manquants pour RetroArch (Wii)",
                        variable=sysfiles_var).grid(row=6, column=0, columnspan=3,
                                                    sticky="w", pady=(2, 2))
        wiimote_var = tk.BooleanVar(value=bool(cfg.get("configure_wiimote", False)))
        ttk.Checkbutton(body,
                        text="Manette Wii : configurer la Wiimote réelle + pointeur au lancement (Dolphin Bar)",
                        variable=wiimote_var).grid(row=7, column=0, columnspan=3,
                                                   sticky="w", pady=(2, 2))
        ttk.Label(body, text="Le pseudo et le port netplay se règlent dans « Jouer en ligne ».",
                  style="Dim.TLabel").grid(row=8, column=0, columnspan=3, sticky="w")

        def save() -> None:
            cfg["site_url"] = site_var.get().strip() or "https://retro.kirbytrim.buzz"
            cfg["roms_dir"] = roms_var.get().strip()
            cfg["download_missing_roms"] = bool(download_var.get())
            cfg["auto_sync_saves"] = bool(auto_var.get())
            cfg["install_dolphin_sysfiles"] = bool(sysfiles_var.get())
            cfg["configure_wiimote"] = bool(wiimote_var.get())
            cfg.setdefault("retroarch", {})
            cfg["retroarch"]["path"] = ra_var.get().strip()
            cfg["retroarch"]["cores_dir"] = cores_var.get().strip()
            save_config(cfg)
            self.covers.update_config(cfg["site_url"], cfg["roms_dir"])
            win.destroy()
            self._set_status("Paramètres enregistrés")
            self.refresh_library()

        buttons = ttk.Frame(body)
        buttons.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        ttk.Button(buttons, text="Diagnostic…", command=self.open_doctor).pack(side="left")
        ttk.Button(buttons, text="Manette Wii…",
                   command=self._wiimote_dialog).pack(side="left", padx=8)
        ttk.Button(buttons, text="Associer kirbyretro://",
                   command=self._install_protocol).pack(side="left", padx=8)
        ttk.Button(buttons, text="Enregistrer", command=save).pack(side="right")
        ttk.Button(buttons, text="Annuler", command=win.destroy).pack(side="right", padx=8)

    def open_doctor(self) -> None:
        win, body = self._dialog("Diagnostic", 900, 560)
        wrap = ttk.Frame(body)
        wrap.pack(fill="both", expand=True)
        text = tk.Text(wrap, wrap="word", relief="flat", bd=0, highlightthickness=1,
                       highlightbackground=LINE, bg=FIELD, fg=FG, font="TkFixedFont")
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
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
        ttk.Button(body, text="Fermer", command=win.destroy).pack(side="right", pady=(10, 0))

    def _wiimote_dialog(self) -> None:
        from . import wiimote

        win, body = self._dialog("Manette Wii — Dolphin Bar", 640, 330)
        info = tk.Label(body, text="", justify="left", anchor="w")
        info.pack(fill="x", pady=(0, 10))

        def refresh() -> None:
            state = wiimote.status()
            bar = "oui" if state["bar"] else "non (branche le Dolphin Bar en USB)"
            if state["access"] is True:
                access = "OK"
            elif state["access"] is False:
                access = "refusé — clique sur « Autoriser le Dolphin Bar »"
            else:
                access = "non vérifiable (allume la Wiimote avec le bouton SYNC)"
            conf = "à jour" if state["configured"] else "sera appliqué au prochain lancement Wii"
            info.configure(text=(
                f"Dolphin Bar branché : {bar}\n"
                f"Accès du système : {access}\n"
                f"Configuration RetroArch : {conf}\n\n"
                "Dans RetroArch, la Wiimote pilote le joueur 1, pointeur inclus\n"
                "(comme dans Dolphin natif). Règle au besoin la position de la\n"
                "sensor bar dans les options du core Dolphin."
            ))

        def apply_now() -> None:
            note = wiimote.apply()
            self._set_status(note or "Manette Wii : RetroArch était déjà configuré")
            refresh()

        def allow() -> None:
            try:
                message = wiimote.install_udev_rule()
            except Exception as exc:  # noqa: BLE001
                self._show_error(f"Règle Dolphin Bar : {exc}")
                return
            self._set_status(message)
            refresh()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Configurer RetroArch maintenant",
                   command=apply_now).pack(side="left")
        ttk.Button(buttons, text="Autoriser le Dolphin Bar (mot de passe)",
                   command=allow).pack(side="left", padx=8)
        ttk.Button(buttons, text="Fermer", command=win.destroy).pack(side="right")
        refresh()

    def _about(self) -> None:
        win, body = self._dialog("À propos", 560, 280)
        lines = [
            f"Kirby Retro Launcher {__version__}",
            "",
            "Launcher natif du site Retro : catalogue des jeux, téléchargement",
            "des ROMs manquantes, lancement dans RetroArch ou un émulateur natif,",
            "netplay et transfert des sauvegardes.",
            "",
            f"Site : {self.config_data.get('site_url') or ''}",
            "Code source : github.com/Trimisdumb/kirby-retro (licence MIT)",
        ]
        for line in lines:
            ttk.Label(body, text=line).pack(anchor="w")
        ttk.Button(body, text="Fermer", command=win.destroy).pack(side="right", pady=(12, 0))

    def _install_protocol(self) -> None:
        try:
            message = install_protocol()
            self._set_status(message if isinstance(message, str) else "Protocole installé")
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"Protocole kirbyretro:// : {exc}")

    def _open_netplay(self, game: dict[str, Any]) -> None:
        title = str(game.get("title") or game.get("file") or "?")
        win, body = self._dialog(f"Jouer en ligne — {title}", 660, 620)
        cfg = self.config_data.setdefault("netplay", {})

        ttk.Label(body, text=f"{game.get('_label') or game.get('_system')} · netplay RetroArch",
                  style="Dim.TLabel").pack(anchor="w")

        top = ttk.Frame(body)
        top.pack(fill="x", pady=(10, 4))
        ttk.Label(top, text="Pseudo").pack(side="left")
        nick_var = tk.StringVar(value=str(cfg.get("nickname") or "Kirby"))
        ttk.Entry(top, textvariable=nick_var, width=14).pack(side="left", padx=(6, 14))
        ttk.Label(top, text="Port").pack(side="left")
        port_var = tk.StringVar(value=str(cfg.get("port") or DEFAULT_PORT))
        ttk.Entry(top, textvariable=port_var, width=6).pack(side="left", padx=6)

        mode = tk.StringVar(value="host")
        relay_var = tk.BooleanVar(value=bool(cfg.get("use_relay", False)))
        address_var = tk.StringVar(value=str(cfg.get("last_host") or ""))
        password_var = tk.StringVar(value="")

        modes = ttk.Frame(body)
        modes.pack(fill="x", pady=(8, 2))
        host_frame = ttk.Frame(body)
        join_frame = ttk.Frame(body)
        pass_frame = ttk.Frame(body)

        def swap() -> None:
            host_frame.pack_forget()
            join_frame.pack_forget()
            pass_frame.pack_forget()
            if mode.get() == "host":
                host_frame.pack(fill="x", pady=4)
                pass_frame.pack(fill="x")
            else:
                join_frame.pack(fill="x", pady=4)

        ttk.Radiobutton(modes, text="Héberger", value="host", variable=mode,
                        command=swap).pack(side="left", padx=(0, 18))
        ttk.Radiobutton(modes, text="Rejoindre", value="join", variable=mode,
                        command=swap).pack(side="left")

        addresses = candidate_addresses()
        values = [f"{tag} — {ip}" for tag, ip in addresses] or ["(aucune adresse détectée)"]

        ttk.Label(host_frame, text="Adresse à donner à ton ami :").pack(anchor="w", pady=(8, 2))
        line = ttk.Frame(host_frame)
        line.pack(fill="x")
        combo = ttk.Combobox(line, values=values, width=30, state="readonly")
        combo.current(0)
        combo.pack(side="left")

        def copy_address() -> None:
            if not addresses:
                return
            index = min(max(combo.current(), 0), len(addresses) - 1)
            self.clipboard_clear()
            self.clipboard_append(f"{addresses[index][1]}:{port_var.get().strip() or DEFAULT_PORT}")
            self._set_status("Adresse copiée — colle-la à ton ami")

        ttk.Button(line, text="Copier", command=copy_address).pack(side="left", padx=8)
        ttk.Checkbutton(
            host_frame,
            text="Relais RetroArch (aucun port à ouvrir — l'ami rejoint via le menu Netplay)",
            variable=relay_var,
        ).pack(anchor="w", pady=(8, 2))
        ttk.Label(host_frame,
                  text="Sans relais : ton ami doit être sur ton Tailscale ou ton réseau local "
                       "(sinon ouvre le port UDP sur ta box). Windows : accepte le pare-feu.",
                  style="Dim.TLabel", wraplength=560, justify="left").pack(anchor="w")

        ttk.Label(pass_frame, text="Mot de passe (optionnel, pour héberger)").pack(anchor="w",
                                                                                  pady=(8, 2))
        ttk.Entry(pass_frame, textvariable=password_var, width=22).pack(anchor="w")

        ttk.Label(join_frame, text="Adresse donnée par ton ami :").pack(anchor="w", pady=(8, 2))
        ttk.Entry(join_frame, textvariable=address_var, width=32).pack(anchor="w")
        ttk.Label(join_frame,
                  text="Il clique Héberger puis Copier et t'envoie l'adresse.\n"
                       "S'il utilise le relais : RetroArch → Netplay → actualise → rejoins son pseudo.",
                  style="Dim.TLabel", justify="left").pack(anchor="w", pady=(4, 0))

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

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", side="bottom", pady=(12, 4))
        ttk.Button(buttons, text="Lancer en ligne", command=start).pack(side="right")
        ttk.Button(buttons, text="Annuler", command=win.destroy).pack(side="right", padx=8)
        ttk.Label(body,
                  text="Netplay : idéal NES / SNES / Mega Drive / GBA / PSX · variable N64 · "
                       "pas dispo DS / Wii / PSP.\nMême jeu et même core chez les deux — "
                       "les ROMs se téléchargent toutes seules.",
                  style="Dim.TLabel", justify="left").pack(anchor="w", pady=(6, 0))
        swap()

    # sauvegardes
    def _open_saves(self, game: dict[str, Any]) -> None:
        title = str(game.get("title") or game.get("file") or "?")
        system = game["_system"]
        roms_dir = str(self.config_data.get("roms_dir") or "") or None
        cores_dir = str((self.config_data.get("retroarch") or {}).get("cores_dir") or "") or None
        rom_path: Path | None = local_rom_path(roms_dir, system, game["file"]) if roms_dir else None
        if rom_path is not None and not rom_path.is_file():
            rom_path = None
        win, body = self._dialog(f"Sauvegardes — {title}", 900, 620)

        native = find_native(system)
        native_name = Path(native).name if native else ""
        if not native_name:
            flat = flatpak_native(system)
            native_name = flat[1] if flat else ""
        if not native_name and system in ("wii", "gamecube"):
            if any(root.is_dir() for _label, root in saves_mod.dolphin_roots()):
                native_name = "Dolphin (natif)"
        target_dir, why = saves_mod.retroarch_target_dir(system, game["file"], cores_dir=cores_dir)

        ttk.Label(body, text=f"Cible RetroArch : {target_dir if target_dir else '—'}").pack(anchor="w")
        ttk.Label(body, text=why, style="Dim.TLabel", wraplength=850,
                  justify="left").pack(anchor="w")
        if native_name:
            ttk.Label(body, text=f"Émulateur natif détecté : {native_name}",
                      style="Dim.TLabel").pack(anchor="w")

        wrap = ttk.Frame(body)
        wrap.pack(fill="both", expand=True, pady=(10, 6))
        table = ttk.Treeview(wrap, columns=("source", "file", "size", "date"),
                             show="headings", selectmode="extended", height=6)
        for key, text, width, anchor in (
            ("source", "Source", 210, "w"),
            ("file", "Fichier", 370, "w"),
            ("size", "Taille", 80, "e"),
            ("date", "Date", 150, "w"),
        ):
            table.heading(key, text=text)
            table.column(key, width=width, anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        table.pack(fill="both", expand=True)

        note = ttk.Label(body, text="", style="Dim.TLabel", wraplength=850, justify="left")
        note.pack(anchor="w", pady=(0, 6))
        state: dict[str, list[saves_mod.SaveFile]] = {"files": []}

        def show(message: str, color: str = DIM) -> None:
            note.configure(text=message, foreground=color)

        def refresh() -> None:
            table.delete(*table.get_children())
            state["files"] = saves_mod.find_saves(
                system, game["file"], roms_dir, rom_path=rom_path
            )
            for idx, save in enumerate(state["files"]):
                table.insert("", "end", iid=f"s{idx}",
                             values=(save.source, save.path.name,
                                     f"{save.size_ko()} Ko", save.date()))
            if state["files"]:
                best = next((i for i, save in enumerate(state["files"])
                             if not save.source.startswith("RetroArch")), 0)
                table.selection_set(f"s{best}")
                show("")
            else:
                show("Aucune sauvegarde trouvée pour ce jeu.")

        def selected() -> list[saves_mod.SaveFile]:
            out: list[saves_mod.SaveFile] = []
            for iid in table.selection():
                idx = int(iid[1:])
                if 0 <= idx < len(state["files"]):
                    out.append(state["files"][idx])
            return out

        def do_retroarch() -> None:
            files = selected()
            if not files:
                show("Sélectionne d'abord une sauvegarde dans la liste.", DANGER)
                return
            try:
                show(saves_mod.import_to_retroarch(system, game["file"], files, cores_dir=cores_dir), OK)
            except saves_mod.SaveError as exc:
                show(str(exc), DANGER)
            except Exception as exc:  # noqa: BLE001
                show(f"Échec de la copie : {exc}", DANGER)
            refresh()

        def do_native() -> None:
            files = selected()
            if not files:
                show("Sélectionne d'abord une sauvegarde dans la liste.", DANGER)
                return
            try:
                show(saves_mod.import_to_native(system, game["file"], files[0], roms_dir), OK)
            except saves_mod.SaveError as exc:
                show(str(exc), DANGER)
            except Exception as exc:  # noqa: BLE001
                show(f"Échec de la copie : {exc}", DANGER)

        def do_export() -> None:
            files = selected()
            if not files:
                show("Sélectionne d'abord une sauvegarde dans la liste.", DANGER)
                return
            dest = filedialog.asksaveasfilename(
                title="Exporter une copie de la sauvegarde",
                initialfile=files[0].path.name,
            )
            if not dest:
                return
            try:
                path = saves_mod.export_copy(files[0], Path(dest))
                show(f"Copie exportée vers {path}", OK)
            except Exception as exc:  # noqa: BLE001
                show(f"Échec de l'export : {exc}", DANGER)

        def do_choose() -> None:
            chosen = filedialog.askopenfilename(
                title="Choisir un fichier de sauvegarde (export du navigateur, autre émulateur…)",
            )
            if not chosen:
                return
            save = saves_mod.SaveFile.from_path(Path(chosen), system)
            state["files"].append(save)
            iid = f"s{len(state['files']) - 1}"
            home = str(Path.home())
            shown = str(save.path).replace(home, "~", 1)
            table.insert("", "end", iid=iid,
                         values=(save.source, shown, f"{save.size_ko()} Ko", save.date()))
            table.selection_set(iid)
            show("Fichier ajouté : tu peux l'importer vers RetroArch.")

        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="Importer vers RetroArch", command=do_retroarch).pack(side="left")
        if native_name:
            ttk.Button(row, text=f"Vers {native_name}", command=do_native).pack(side="left", padx=6)
        ttk.Button(row, text="Exporter une copie…", command=do_export).pack(side="left", padx=6)
        ttk.Button(row, text="Choisir un fichier…", command=do_choose).pack(side="left")
        ttk.Button(row, text="Actualiser", command=refresh).pack(side="right")
        ttk.Label(body,
                  text="Sauvegardes de jeu uniquement (pas les savestates). Chaque copie garde "
                       "l'ancienne version en .bak ; au lancement, la plus récente est importée "
                       "automatiquement (option dans Paramètres).",
                  style="Dim.TLabel", wraplength=850, justify="left").pack(anchor="w", pady=(8, 0))
        refresh()

    # fermeture
    def on_close(self) -> None:
        try:
            self.destroy()
        except tk.TclError:
            pass


def run_gui() -> None:
    app = LauncherApp()
    app.mainloop()


main = run_gui
