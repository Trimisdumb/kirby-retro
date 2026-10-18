"""Point d'entrée de l'exécutable autonome (PyInstaller).

En développement : python kirby_retro_launcher.py
"""
from retro_launcher.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
