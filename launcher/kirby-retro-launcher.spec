# -*- mode: python ; coding: utf-8 -*-
"""Exécutable unique multi-plateforme.

    pyinstaller --clean --noconfirm kirby-retro-launcher.spec

Le binaire obtenu (dossier dist/) embarque Python : aucune installation
requise chez le joueur. GitHub Actions utilise ce même fichier pour publier
le .exe Windows et le binaire Linux (voir .github/workflows/build-launcher.yml).
"""

a = Analysis(
    ["kirby_retro_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[],
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
