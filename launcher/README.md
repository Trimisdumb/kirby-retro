# Kirby Retro Launcher

Launcher **natif multi-plateforme** (Windows, Linux, macOS) pour [retro.kirbytrim.buzz](https://retro.kirbytrim.buzz).

Téléchargement + guide d'installation : **<https://retro.kirbytrim.buzz/client.html>**

Le site reste le catalogue (style Wii). Ce programme **lance les jeux en local** avec :

1. **RetroArch** (recommandé — un seul outil, tous les cores)
2. **Émulateurs natifs** si installés (melonDS, DuckStation, etc.) — prioritaire pour DS / N64 / PSX

Plus d’émulation WASM lourde dans le navigateur pour ces machines.

## Nouveautés v1.7.0

- **Interface repensée, plus sobre** : fenêtre classique (barre de titre, redimensionnable), **barre de menus** (Fichier, Émulation, Options, Affichage, Aide), **barre d'outils** (Démarrer, En ligne, Sauvegardes, Rafraîchir, Paramètres), **liste de jeux** avec bannières, tri par colonne, filtre par console et **barre d'état**. Les polices pixel et les effets néon sont retirés.
- La chiptune, le netplay, les sauvegardes et le téléchargement automatique des ROMs restent inchangés.

## Nouveautés v1.6.0

- **Sauvegardes entre émulateurs** : nouveau bouton **SAUVEGARDES** (aussi dans le clic droit) — le launcher liste les sauvegardes de jeu qu’il trouve, puis **IMPORTER VERS RETROARCH**, **VERS** l’émulateur natif, **EXPORTER UNE COPIE** ou **CHOISIR UN FICHIER** (export du navigateur, autre émulateur…). Conversion au passage : les .dsv DeSmuME perdent leur en-tête, les fichiers N64 (.eep/.sra/.fla/.mpk) sont fusionnés dans le .srm attendu par RetroArch — et inversement.
- **Rien n’est écrasé** : avant chaque copie, la sauvegarde déjà en place est conservée en `.bak-<date>`.

## Nouveautés v1.5.0

- **Habillage rétro-arcade complet** : fenêtre sans bordure à liseré néon, fond dégradé violet/orangé avec **scanlines CRT**, polices pixel (**Press Start 2P** + **VT323**), cartes de jeux avec **jaquette** (téléchargée automatiquement, cache local), **glow au survol**, sélection cyan.
- **Recherche + filtres par console** dynamiques, **clic droit** = menu (jouer, jouer en ligne, copier le titre), double-clic = jouer.
- **Musique chiptune** synthétisée en pur Python et jouée en boucle — bouton **MUSIQUE** dans la barre de titre (désactivable ; ta propre musique est possible dans Paramètres).
- Fenêtre déplaçable à la souris, boutons minimiser / fermer maison, barre de statut en français.

## Nouveautés v1.4.0

- **Jouer en ligne (netplay RetroArch)** : bouton **🌐 En ligne** — héberger ou rejoindre une partie en un clic. Adresse **Tailscale** / réseau local détectée automatiquement (bouton « Copier »), **relais RetroArch** optionnel (aucun port à ouvrir), pseudo + port + dernière adresse mémorisés.
- Le **`doctor`** affiche l’état netplay et les adresses à donner à l’ami.

## Nouveautés v1.3.0

- **Beaucoup plus de consoles** : Sega 32X, Sega Saturn, Dreamcast, GameCube, Wii, PS2, PSP, 3DS, arcade (FBNeo / MAME…), Amstrad CPC, Apple II, PC-88, Pokémon Mini.
- **Un core par console, plusieurs choix** : le launcher prend celui que tu as installé (ex. Saturn : `mednafen_saturn`, `kronos`, `yabause`, `yabasanshiro` ; arcade : `fbneo`, `mame2003_plus`, `mame2003`, `fbalpha2012`).
- **Cores c64/lynx/pce enrichis** (`vice_x64sc`, `mednafen_lynx`, `mednafen_supergrafx` en secours).

## Nouveautés v1.2.0

- **Détection RetroArch universelle** : paquets système (`dnf`, `apt`, `pacman`…), Flatpak, snap, AppImage, portable Windows — cores cherchés dans `~/.config/retroarch/cores`, `/usr/lib*/libretro`, le dossier Flatpak, et celui déclaré dans `retroarch.cfg` (`libretro_directory`). Fini les « Aucun émulateur configuré » sur Fedora & co.
- **Fenêtre de progression** au lancement depuis le navigateur : tu vois le téléchargement, le lancement, et **les erreurs s’affichent** (plus de « rien ne se passe »).
- **Protocole `kirbyretro://`** : entrée visible dans le menu applications, icône, nettoyage des associations parasites, `update-desktop-database` systématique.
- **Cores alternatifs** : si `melonds` manque, `melondsds` ou `desmume` prennent le relais (et inversement), y compris `desmume2015`.
- **`doctor` plus bavard** : tkinter, dossiers cores explorés, cores trouvés par console.

## Prérequis

- **Python 3.10+** (stdlib uniquement, aucune dépendance pip obligatoire)
- **tkinter** (interface graphique) : livré avec Python sur Windows/macOS ; sur Linux :
  - Fedora : `sudo dnf install python3-tkinter`
  - Debian/Ubuntu : `sudo apt install python3-tk`
- **RetroArch** + cores libretro  
  - Linux : `sudo dnf install retroarch` / `sudo apt install retroarch` ou Flatpak  
  - Windows / macOS : [retroarch.com](https://www.retroarch.com/) → Online Updater → Manage Cores
- Optionnel : melonDS, DuckStation, simple64…

## Installation rapide

```bash
cd launcher
# Linux / macOS
./run.sh

# Windows
run.bat
```

Au premier lancement, **tout est préconfiguré** :

- le **dossier ROMs par défaut** est `~/KirbyRetroROMs` (`%USERPROFILE%\KirbyRetroROMs` sur Windows) — créé automatiquement ;
- les ROMs absentes sont **téléchargées depuis le site** au premier clic sur un jeu ;
- RetroArch + cores sont détectés automatiquement (Flatpak, paquets système `dnf`/`apt`/`pacman`, snap, portable).

Pour tout changer : **Paramètres** →

| Champ | Exemple |
|--------|---------|
| URL du site | `https://retro.kirbytrim.buzz` |
| Dossier ROMs | dossier contenant `nes/`, `nds/`, `n64/`… |
| RetroArch | chemin vers `retroarch` / `retroarch.exe` |
| Dossier cores | dossier des `*_libretro.so` / `.dll` |

## Lancer un jeu en ligne de commande

```bash
./run.sh play nds "Mario Kart DS (Europe).zip"
./run.sh play --url "kirbyretro://play?system=n64&file=Super%20Mario%2064.zip"
```

## Jouer en ligne (netplay)

Bouton **« 🌐 En ligne »** de l’interface (jeu sélectionné dans la liste) :

1. **Héberger** : choisis un pseudo puis « Héberger » — le launcher affiche ton adresse
   (**Tailscale** en priorité, sinon réseau local) avec un bouton **« 📋 Copier »**.
   Envoie-la à ton ami. Coche le **relais RetroArch** pour jouer **sans ouvrir de port** :
   ton ami rejoint alors via *RetroArch → Netplay* (actualise, cherche ton pseudo) ;
   un mot de passe optionnel protège la partie.
2. **Rejoindre** : colle l’adresse donnée par l’hôte, clique « Lancer la partie en ligne ».

Notes :

- Même **jeu** et même **core** chez les deux joueurs — le launcher télécharge la ROM du site tout seul ;
- idéal sur **NES, SNES, Mega Drive, GBA, PSX** ; variable sur N64 ; pas disponible pour DS / Wii / PSP ;
- hors Tailscale / réseau local, ouvre le port **UDP 55435** sur ta box
  (Windows : accepte le message du pare-feu pour RetroArch) ;
- pseudo, port et dernière adresse sont mémorisés (modifiables à chaque lancement).

## Sauvegardes

Le bouton **SAUVEGARDES** (ou clic droit sur un jeu) liste les sauvegardes trouvées pour ce jeu, puis :

- **IMPORTER VERS RETROARCH** — écrit le `.srm` au bon endroit (dossier lu dans `retroarch.cfg`). Plusieurs fichiers sélectionnés (N64 : .eep/.sra/.fla/.mpk) sont fusionnés dans l’ordre attendu.
- **VERS …** — copie vers l’émulateur natif détecté (melonDS, simple64, DuckStation…), en redécoupant un `.srm` N64 si besoin.
- **EXPORTER UNE COPIE** / **CHOISIR UN FICHIER** — pour passer par un fichier (export du navigateur, sauvegarde d’un autre PC…).

Conversions automatiques : `.dsv` DeSmuME → sauvegarde brute DS, `.eep`/`.sra`/`.fla`/`.mpk` ↔ `.srm` N64. Ça ne concerne que les sauvegardes de jeu (pas les savestates). Avant chaque écriture, la version en place est gardée en `.bak-<date>`.

## Protocole `kirbyretro://` (bouton « Launcher natif » du site)

Le site ouvre ce genre de lien :

```text
kirbyretro://play?system=nds&file=MonJeu.nds
```

### Enregistrement automatique (recommandé)

```bash
# Linux
./run.sh install-protocol

# Windows
run.bat install-protocol
```

- **Linux** : écrit `~/.local/share/applications/kirbyretro.desktop` et l’enregistre via `xdg-mime`. Aucun droit root.
- **Windows** : écrit `HKCU\Software\Classes\kirbyretro` (+ `HKLM` si droits admin) — **pas besoin d’administrateur**.
- **macOS** : non pris en charge automatiquement (voir ci-dessous).

C’est aussi disponible dans l’interface : **Paramètres → « Associer les liens kirbyretro:// »**.

### Si le lien ne s’ouvre pas dans Firefox

Firefox demande une première fois l’autorisation, puis mémorise le choix. En cas de souci :

1. Vérifie l’association : `xdg-mime query default x-scheme-handler/kirbyretro` doit répondre `kirbyretro.desktop` ;
2. Dans Firefox : **Paramètres → Général → Applications**, cherche `kirbyretro` et choisis « Toujours demander » ;
3. **Redémarre Firefox** après `./run.sh install-protocol` (il lit les associations au démarrage) ;
4. En dernier recours : `about:config` → supprime les clés `network.protocol-handler.*.kirbyretro`.

Sur le site, un bandeau de secours s’affiche aussi sous le jeu : tu peux **jouer dans le navigateur** en un clic si le launcher ne s’ouvre pas.

### Enregistrement manuel (macOS, ou si besoin)

**macOS** — créer une app Automator « Ouvrir un document », action « Exécuter un script shell » :

```bash
/chemin/vers/launcher/run.sh play --url "$1"
```

**Linux (manuel)** — fichier `~/.local/share/applications/kirbyretro.desktop` :

```ini
[Desktop Entry]
Name=Kirby Retro Launcher
Exec=bash /chemin/vers/launcher/run.sh play --url %u
Type=Application
MimeType=x-scheme-handler/kirbyretro;
```

Puis : `xdg-mime default kirbyretro.desktop x-scheme-handler/kirbyretro`

## Diagnostic

En cas de souci (jeu qui ne se lance pas, RetroArch introuvable…) :

```bash
./run.sh doctor      # Linux / macOS
run.bat doctor       # Windows
```

Affiche : config, accès au site, interface tkinter, dossier ROMs, RetroArch, **dossiers de cores explorés**,
cores manquants par console, émulateurs natifs détectés et état du protocole `kirbyretro://`.
Disponible aussi dans l’interface : **Paramètres → Diagnostic**.

## Stratégie de lancement

| Console | Ordre |
|---------|--------|
| nds, n64, psx | 1) émulateur natif configuré/détecté 2) RetroArch |
| autres | 1) RetroArch 2) natif |

## Fichier de config

Stocké dans :

- Linux : `~/.config/KirbyRetroLauncher/config.json`
- Windows : `%APPDATA%\KirbyRetroLauncher\config.json`
- macOS : `~/Library/Application Support/KirbyRetroLauncher/config.json`

## Cores conseillés par console

| Console | Core |
|---------|------|
| nes | `fceumm_libretro` (ou `mesen2`, `nestopia`, `mesen-s`) |
| snes | `snes9x_libretro` (ou `bsnes`, `mesen-s`) |
| gb / gba | `gambatte_libretro` / `mgba_libretro` |
| nds | `melondsds_libretro` (ou `melonds_libretro`, `desmume_libretro`, `desmume2015_libretro`) |
| n64 | `mupen64plus_next_libretro` |
| psx | `pcsx_rearmed_libretro` (ou `swanstation`, `mednafen_psx`) |
| ps2 | `pcsx2_libretro` |
| psp | `ppsspp_libretro` |
| segaMD / segaMS / segaGG / segaCD / sega32x | `genesis_plus_gx_libretro` / `picodrive_libretro` |
| segaSaturn | `mednafen_saturn_libretro` (ou `kronos`, `yabause`, `yabasanshiro`) |
| dreamcast | `flycast_libretro` |
| gamecube / wii | `dolphin_libretro` |
| 3ds | `azahar_libretro` (ou `citra2018_libretro`) |
| arcade | `fbneo_libretro` (ou `mame2003_plus`, `mame2003`, `fbalpha2012`) |
| pce / atari2600 / lynx / vb | `mednafen_pce` (`mednafen_pce_fast`, `mednafen_supergrafx`) / `stella2014` / `handy` / `mednafen_vb` |
| c64 | `vice_x64sc_libretro` (ou `vice_x64_libretro`) |
| cpc / apple2 / pc88 / pokemini | `cap32` (`crocods`) / `applewin` / `quasi88` / `pokemini` |

## Pourquoi ce choix ?

L’émulation DS/N64 dans le navigateur (WASM) reste limitée. Un launcher natif + RetroArch/melonDS donne de **vraies perfs**, manettes Linux/Windows fiables, et ton site continue de gérer catalogue, jaquettes et uploads.

## Crédits

- Code du site et du launcher : licence **MIT** — sources sur [github.com/Trimisdumb/kirby-retro](https://github.com/Trimisdumb/kirby-retro).
- Chiptune : boucle 8-bit **générée localement** par le launcher (aucun fichier audio téléchargé ; s'active ou se coupe dans **Options → Musique**).
- Jaquettes : récupérées de ton site et mises en cache dans `~/.cache/KirbyRetroLauncher/covers/` — rien n’est envoyé ailleurs.
