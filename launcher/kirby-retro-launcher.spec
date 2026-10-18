# -*- mode: python ; coding: utf-8 -*-
"""Exécutable unique multi-plateforme.

    pyinstaller --clean --noconfirm kirby-retro-launcher.spec

Le binaire obtenu (dossier dist/) embarque Python : aucune installation
requise chez le joueur. GitHub Actions utilise ce même fichier pour publier
le .exe Windows et le binaire Linux (voir .github/workflows/build-launcher.yml).
"""

import os

# Copie de secours des certificats (Linux) : utilisée si la machine du joueur
# n'a pas de magasin à l'emplacement attendu par l'OpenSSL embarqué.
_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
_datas = [(_CA_BUNDLE, "certs")] if os.path.exists(_CA_BUNDLE) else []

a = Analysis(
    ["kirby_retro_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pip", "setuptools", "wheel"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="kirby-retro-launcher",
    icon="icon.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windows : pas de fenêtre de console derrière l'interface
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
