"""Correspondance console → core RetroArch (.dll / .so / .dylib)."""

# id système (API site) → cores acceptables, par ordre de préférence.
# Les noms changent parfois selon les versions de RetroArch (ex. melonds →
# melondsds) : on accepte plusieurs cores pour utiliser ceux déjà installés.
RETROARCH_CORES: dict[str, tuple[str, ...]] = {
    "nes": ("fceumm_libretro", "mesen2_libretro", "nestopia_libretro", "mesen-s_libretro"),
    "snes": ("snes9x_libretro", "bsnes_libretro", "mesen-s_libretro"),
    "gb": ("gambatte_libretro", "sameboy_libretro", "gearboy_libretro"),
    "gba": ("mgba_libretro", "gpsp_libretro", "vba_next_libretro"),
    "n64": ("mupen64plus_next_libretro", "parallel_n64_libretro"),
    "nds": ("melondsds_libretro", "melonds_libretro", "desmume_libretro", "desmume2015_libretro"),
    "psx": ("pcsx_rearmed_libretro", "swanstation_libretro", "mednafen_psx_libretro", "mednafen_psx_hw_libretro"),
    "ps2": ("pcsx2_libretro",),
    "psp": ("ppsspp_libretro",),
    "segaMD": ("genesis_plus_gx_libretro", "picodrive_libretro"),
    "segaMS": ("genesis_plus_gx_libretro", "picodrive_libretro"),
    "segaGG": ("genesis_plus_gx_libretro", "picodrive_libretro"),
    "segaCD": ("genesis_plus_gx_libretro", "picodrive_libretro"),
    "sega32x": ("picodrive_libretro",),
    "segaSaturn": ("mednafen_saturn_libretro", "kronos_libretro", "yabause_libretro", "yabasanshiro_libretro"),
    "dreamcast": ("flycast_libretro",),
    "gamecube": ("dolphin_libretro",),
    "wii": ("dolphin_libretro",),
    "3ds": ("azahar_libretro", "citra2018_libretro", "citra_libretro"),
    "arcade": ("fbneo_libretro", "mame2003_plus_libretro", "mame2003_libretro", "fbalpha2012_libretro"),
    "pce": ("mednafen_pce_libretro", "mednafen_pce_fast_libretro", "mednafen_supergrafx_libretro"),
    "atari2600": ("stella2014_libretro", "stella_libretro"),
    "lynx": ("handy_libretro", "mednafen_lynx_libretro"),
    "c64": ("vice_x64sc_libretro", "vice_x64_libretro"),
    "vb": ("mednafen_vb_libretro", "beetle_vb_libretro"),
    "cpc": ("cap32_libretro", "crocods_libretro"),
    "apple2": ("applewin_libretro",),
    "pc88": ("quasi88_libretro",),
    "pokemini": ("pokemini_libretro",),
}

# Émulateurs standalone connus (détectés automatiquement si dans le PATH)
NATIVE_HINTS = {
    "nds": ["melonDS", "melonds", "melonDS-DS"],
    "n64": ["simple64-gui", "parallel-launcher", "mupen64plus"],
    "psx": ["duckstation-qt", "duckstation"],
    "ps2": ["pcsx2-qt", "pcsx2"],
    "psp": ["ppsspp-qt", "ppsspp"],
    "segaSaturn": ["mednafen"],
    "dreamcast": ["flycast", "redream"],
    "gamecube": ["dolphin-emu", "dolphin"],
    "wii": ["dolphin-emu", "dolphin"],
    "snes": ["snes9x-gtk", "snes9x"],
    "nes": ["fceux", "mesen"],
    "gba": ["mgba-qt", "mgba"],
    "gb": ["sameboy", "mgba-qt"],
    "cpc": ["caprice32"],
    "pc88": ["quasi88"],
}
