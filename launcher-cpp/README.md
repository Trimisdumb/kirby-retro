# Kirby Retro Launcher — version C++ (Qt 6)

Portage du launcher (initialement Python/Tkinter) vers **C++/Qt 6**, comme les
émulateurs du projet (Dolphin, Cemu…). La version Python reste la version
livrée sur le site le temps que le portage soit complet.

## État actuel (v0.1)

- Bibliothèque du site avec **jaquettes** (cache partagé : `~/.cache/KirbyRetroLauncher/covers/`)
- **Recherche** et filtre par console, tri par colonne
- **Téléchargement automatique des ROMs** manquantes (barre de progression)
- Détection **RetroArch** (paquet système, Flatpak, Snap, AppImage) et des **cores**
- Lancement **RetroArch** ou **émulateur natif** selon la console (`prefer_native_for`)
- **Paramètres** (site, dossier ROMs, RetroArch, cores)
- Même fichier de configuration que la version Python — les deux cohabitent

## À venir

- Sauvegardes (détection + import) — pour l'instant, utiliser la version Python
- Netplay, protocole `kirbyretro://`, diagnostic

## Construire

```bash
sudo dnf install qt6-qtbase-devel cmake gcc-c++     # Fedora
sudo apt install qt6-base-dev cmake build-essential # Debian / Ubuntu

cmake -S . -B build -G Ninja
cmake --build build
./build/kirby-retro-launcher-cpp
```
