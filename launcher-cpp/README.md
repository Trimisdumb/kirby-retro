# Kirby Retro Launcher — version C++ (Qt 6)

Portage du launcher (initialement Python/Tkinter) vers **C++/Qt 6**, comme les
émulateurs du projet (Dolphin, Cemu…). La version Python reste disponible sur le
site le temps que le portage soit complet (sauvegardes synchronisées, netplay).

## État actuel (v0.2)

- Bibliothèque du site avec **jaquettes** (cache partagé : `~/.cache/KirbyRetroLauncher/covers/`)
- **Recherche** et filtre par console, tri par colonne
- **Téléchargement automatique des ROMs** manquantes (barre de progression)
- Détection **RetroArch** (paquet système, Flatpak, Snap, AppImage, Windows —
  dont le dossier par défaut `C:\RetroArch-Win64` de l'installateur officiel) et des **cores**
  (dossier de l'exécutable, `retroarch.cfg`, dossiers utilisateur)
- Un **dossier** est accepté à la place de `retroarch.exe` dans les Paramètres
- Lancement **RetroArch** ou **émulateur natif** selon la console (`prefer_native_for`)
- **Paramètres** (site, dossier ROMs, RetroArch, cores)
- **Diagnostic** (menu *Aide → Diagnostic…*, ou `kirby-retro-launcher-cpp --diagnostic`) :
  liste RetroArch, les cores et les émulateurs natifs trouvés — à copier en cas de souci
- Même fichier de configuration que la version Python — les deux cohabitent

## À venir

- Sauvegardes (détection + import) — pour l'instant, utiliser la version Python
- Netplay, protocole `kirbyretro://`, wiimote/Dolphin Bar

## Construire

```bash
sudo dnf install qt6-qtbase-devel cmake gcc-c++     # Fedora
sudo apt install qt6-base-dev cmake build-essential # Debian / Ubuntu

cmake -S . -B build -G Ninja
cmake --build build
./build/kirby-retro-launcher-cpp
```
