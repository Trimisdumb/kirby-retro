"""Retour visuel quand le launcher est ouvert depuis un navigateur (kirbyretro://).

Le navigateur ne montre aucune console : on ouvre une petite fenêtre de
progression et on y affiche les erreurs, pour que l'utilisateur ne reste
jamais devant « rien ne se passe ». Repli : notification notify-send / stderr.
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
from typing import Any

from .config import subprocess_env
from .launch import LaunchError, launch_game

BG = "#e8f6fc"


def _display_available() -> bool:
    if sys.platform == "win32":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def notify_error(message: str) -> None:
    """Signale une erreur sans fenêtre : stderr + notification bureau (Linux)."""
    print(message, file=sys.stderr)
    if sys.platform.startswith("linux") and shutil.which("notify-send"):
        try:
            first = (message.strip().splitlines() or ["Erreur"])[0][:180]
            subprocess.run(
                ["notify-send", "-a", "Kirby Retro Launcher", "-u", "critical", "Échec du lancement", first],
                timeout=10,
                check=False,
                env=subprocess_env(),
            )
        except OSError:
            pass


def run_console(config: dict[str, Any], system: str, file: str) -> int:
    """Lancement classique (terminal) : progression sur stderr."""
    try:
        msg = launch_game(config, system, file, progress=lambda m: print(m, file=sys.stderr))
        print(msg)
        return 0
    except LaunchError as exc:
        notify_error(str(exc))
        return 1


def run_with_feedback(config: dict[str, Any], system: str, file: str) -> int:
    """Lancement depuis le navigateur : petite fenêtre de progression + erreurs visibles."""
    if not _display_available():
        return run_console(config, system, file)
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:  # tkinter absent (paquet python3-tkinter manquant)
        notify_error(
            "Interface graphique indisponible (tkinter manquant).\n"
            "Fedora : sudo dnf install python3-tkinter — Debian/Ubuntu : sudo apt install python3-tk"
        )
        return run_console(config, system, file)

    root = tk.Tk()
    root.title("Kirby Retro Launcher")
    root.configure(bg=BG)
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass

    width, height = 480, 150
    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 3)
    root.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(root, bg=BG, padx=18, pady=14)
    frame.pack(fill="both", expand=True)
    tk.Label(
        frame,
        text="\U0001F3AE Kirby Retro Launcher",
        bg=BG,
        font=("TkDefaultFont", 11, "bold"),
    ).pack(anchor="w")
    status_var = tk.StringVar(value=f"Préparation de {file}…")
    tk.Label(
        frame,
        textvariable=status_var,
        bg=BG,
        wraplength=440,
        justify="left",
    ).pack(anchor="w", pady=(10, 0))

    messages: "queue.Queue[tuple[str, str]]" = queue.Queue()
    state = {"alive": True, "code": 1}

    def worker() -> None:
        try:
            msg = launch_game(config, system, file, progress=lambda m: messages.put(("status", m)))
            messages.put(("done", msg))
        except LaunchError as exc:
            messages.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            messages.put(("error", f"Erreur inattendue : {exc}"))

    def close() -> None:
        state["alive"] = False
        try:
            root.destroy()
        except tk.TclError:
            pass

    def poll() -> None:
        if not state["alive"]:
            return
        while True:
            try:
                kind, payload = messages.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                status_var.set(payload)
            elif kind == "done":
                state["code"] = 0
                status_var.set(f"✓ Lancé — {payload}")
                root.after(900, close)
            else:  # error
                state["code"] = 1
                messagebox.showerror("Kirby Retro Launcher", payload, parent=root)
                close()
                return
        root.after(120, poll)

    root.protocol("WM_DELETE_WINDOW", close)
    threading.Thread(target=worker, daemon=True).start()
    root.after(120, poll)
    root.mainloop()
    return state["code"]
