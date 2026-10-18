# Kirby Retro

Bibliothèque de jeux rétro **jouables dans le navigateur**, auto-hébergée — site Node sans
dépendances + launcher natif Python/Tkinter. En production sur `retro.kirbytrim.buzz`
(serveur Debian, Docker, Cloudflare Tunnel). Les **jaquettes sont récupérées automatiquement**
depuis une base libre, et tout est catalogué dans une **base SQLite**.

- **Émulation** : [EmulatorJS](https://github.com/EmulatorJS/EmulatorJS) (GPLv3) + cores RetroArch,
  **rapatriés en local** par `scripts/fetch-ejs.sh` → aucune dépendance à un CDN à l'exécution.
  Les 4 variantes de chaque core sont présentes : mono-thread, **multi-thread**, WebGL1 et WebGL1+threads.
- **Serveur** : Node 22, **zéro dépendance npm** (`node:http`, `node:fs`, `node:sqlite`).
- **Multithread** : le site sert `Cross-Origin-Opener-Policy` + `Cross-Origin-Embedder-Policy`, ce qui
  expose `SharedArrayBuffer` → `EJS_threads = true` → les cores utilisent tous les cœurs du CPU.
- **Jaquettes** : [libretro-thumbnails](https://thumbnails.libretro.com/) (libre, sans clé API),
  avec correspondance tolérante des noms (`Mario_Kart_DS (Europe) (En_Fr_De_Es_It).zip` → `Mario Kart DS (Europe) (En,Fr,De,Es,It).png`).

## Consoles supportées

| Dossier (`roms/`) | Console | Core | Extensions | Jaquettes |
|---|---|---|---|---|
| `nes` | NES / Famicom | fceumm | nes, fds, unf, unif, zip | ✅ |
| `snes` | Super Nintendo | snes9x | smc, sfc, swc, fig, zip | ✅ |
| `gb` | Game Boy / Color | gambatte | gb, gbc, dmg, zip | ✅ |
| `gba` | Game Boy Advance | mgba | gba, agb, zip | ✅ |
| `n64` | Nintendo 64 | mupen64plus_next | n64, z64, v64, u1, ndd, zip | ✅ |
| `nds` | Nintendo DS | melonds | nds, zip | ✅ |
| `psx` | PlayStation | pcsx_rearmed | cue, chd, pbp, iso, img, mdf (+ bin) | ✅ |
| `segaMD` | Mega Drive / Genesis | genesis_plus_gx | md, gen, smd, bin, zip | ✅ |
| `segaMS` | Master System | smsplus | sms, zip | ✅ |
| `segaGG` | Game Gear | genesis_plus_gx | gg, zip | ✅ |
| `pce` | PC Engine | mednafen_pce | pce, sgx, zip | ✅ |
| `atari2600` | Atari 2600 | stella2014 | a26, bin | ✅ |
| `lynx` | Atari Lynx | handy | lnx, zip | ✅ |
| `c64` | Commodore 64 | vice_x64sc | d64, t64, prg, tap, crt, nib, zip | ✅ |
| `vb` | Virtual Boy | beetle_vb | vb, vboy, zip | ✅ |

> **GameCube / Wii (Dolphin) : impossible dans un navigateur.** Dolphin est un émulateur natif (JIT PowerPC) ;
> en WebAssembly il faudrait un interpréteur — la [doc EmulatorJS](https://emulatorjs.org/docs4devs/cores)
> le dit : *« One frame per 5 seconds with an RTX 5090 + 9950X3D »*.

## Architecture

```
/srv/docker/retro/
├── compose.yaml          # conteneur retro-site (127.0.0.1:8093)
├── src/
│   ├── server.mjs        # HTTP : statique, ROMs, jaquettes, API
│   ├── catalog.mjs       # base SQLite (tables systems + games)
│   └── covers.mjs        # récupération des jaquettes (libretro-thumbnails)
├── public/               # interface (bibliothèque, lecteur, upload, licences)
├── scripts/
│   ├── fetch-ejs.sh      # rapatrie le bundle EmulatorJS + les cores
│   └── fetch-covers.mjs  # récupère les jaquettes en ligne de commande
├── roms/<console>/       # tes ROMs (+ library.json pour les titres, covers/ à la main)
├── covers/<console>/     # jaquettes téléchargées (servi sur /covers/)
├── state/
│   ├── catalog.db        # base SQLite
│   └── libretro-index/   # cache des index libretro (rafraîchi tous les 7 jours)
└── ejs/                  # bundle EmulatorJS (loader, 56 cores, localisation)
```

## Installation / mise à jour

```bash
git clone https://github.com/Trimisdumb/kirby-retro.git
cd kirby-retro
cp .env.example .env                                 # mets-y ton UPLOAD_TOKEN
mkdir -p roms/{nes,snes,gb,gba,n64,nds,psx,segaMD,segaMS,segaGG,pce,atari2600,lynx,c64,vb} covers state
bash scripts/fetch-ejs.sh "$PWD/ejs"                 # ~62 Mo, une seule fois
docker compose up -d --build
curl -s localhost:8093/healthz                       # → ok
```

Aucune ROM n'est fournie : dépose les tiennes dans `roms/<console>/` (l'interface les détecte
au prochain chargement de la bibliothèque).

Après un déploiement, récupérer les jaquettes manquantes :

```bash
docker compose exec retro node scripts/fetch-covers.mjs          # manquantes uniquement
docker compose exec retro node scripts/fetch-covers.mjs --all    # tout retélécharger
docker compose exec retro node scripts/fetch-covers.mjs --system n64,nds
```

## API

| Route | Rôle |
|---|---|
| `GET /api/library` | catalogue complet (SQLite) : consoles, jeux, jaquettes, régions |
| `GET /api/config` | réglages publics (netplay, serveurs ICE) |
| `GET /api/covers/status` | état de la récupération de jaquettes |
| `POST /api/covers/refresh[?system=n64]` | relance la récupération (en-tête `x-upload-token`) |
| `POST /api/upload?system=nes&name=jeu.nes` | dépose une ROM (+ jaquette en tâche de fond) |
| `GET /roms/<console>/<fichier>` | ROM (Range/ETag) |
| `GET /covers/<console>/<fichier>.png` | jaquette |
| `GET /ejs/data/*` | bundle EmulatorJS (cache immuable 1 an) |
| `GET /healthz` | sonde Docker |

## Multijoueur (netplay)

EmulatorJS réserve le netplay au mode *debug* **et** à un drapeau expérimental
(`src/emulator.js` : `netplayEnabled = EJS_DEBUG_XX && EJS_EXPERIMENTAL_NETPLAY`).
Le lecteur reste donc en mode minifié (plus rapide) et bascule à la demande :

- bouton **👥 Jouer à plusieurs** dans l'en-tête du lecteur → recharge la page avec `?netplay=1` ;
- l'icône **👥** apparaît alors dans la barre de l'émulateur : pseudo → créer un salon ou en rejoindre un ;
- les autres joueurs le voient dans la liste (`/list` du serveur) et rejoignent ;
- il faut la **même ROM** chez tout le monde (l'`EJS_gameID` est dérivé du nom de fichier) ;
- seuls les **inputs** circulent entre joueurs (WebRTC) : la latence dépend des connexions, pas du serveur ;
- les serveurs `STUN`/`TURN` (configurables via `NETPLAY_ICE_SERVERS` en JSON dans `.env`) prennent le relais
  si le pair-à-pair échoue (NAT strict, CGNAT).

Serveur : conteneur `netplay` (projet `work/netplay/`), écoute en local sur `3010`, exposé sur
`netplay.kirbytrim.buzz` (WebSocket via le tunnel Cloudflare).

## Client PC — Kirby Retro Launcher (`launcher/`)

Launcher natif multiplateforme (Python + Tkinter, sans dépendance) servi sur **`/client.html`** :

- téléchargements statiques : `public/downloads/kirby-retro-launcher-<version>.zip` (Windows) +
  `.tar.gz` (Linux) — reconstruits depuis `launcher/` (penser à éditer la version dans
  `launcher/retro_launcher/__init__.py` et la page `client.html`) ;
- fusionne le catalogue du site (`/api/library`), télécharge les ROMs manquantes depuis
  `/roms/...` et lance RetroArch (cores) ou un émulateur standalone (melonDS, DuckStation…) ;
- liens `kirbyretro://play?system=…&file=…` : enregistrement via
  `./run.sh install-protocol` / `run.bat install-protocol` (Linux `.desktop` + xdg-mime ;
  Windows `HKCU\Software\Classes\kirbyretro`, + HKLM si admin) ;
- diagnostic intégré : `./run.sh doctor` / `run.bat doctor` (config, site, cores, protocole) ;
- portage **C++/Qt 6** en cours dans `launcher-cpp/` (mêmes serveurs, même config) — la version
  Python reste la version livrée le temps du portage.

## Stabilité et modes d'exécution

Deux profils, commutables en un clic dans l'en-tête du lecteur (choix mémorisé dans le navigateur) :

| Mode | Contenu | Défaut sur |
|---|---|---|
| ⚡ **Performance** | cores multi-thread (`EJS_threads`), WebGL2 | Chromium / Edge / Brave |
| 🛡️ **Compatibilité** | mono-thread, cores WebGL1 si le rendu est logiciel ou sans WebGL2, cache désactivé si le stockage est bloqué | Firefox / Waterfox / LibreWolf |

- URL : `?perf=1` ou `?safe=1` pour forcer un mode (pratique à partager avec un pote).
- Le lecteur **détecte tout seul** : rendu graphique logiciel (SwiftShader/llvmpipe), WebGL2 absent,
  `SharedArrayBuffer` indisponible, `localStorage` bloqué (navigation privée stricte) → il propose le mode adapté.
- En cas de plantage du core (RuntimeError WASM, mémoire, abort…), un **bandeau d'erreur** s'affiche avec un
  bouton « Relancer en mode compatibilité » au lieu d'un écran noir figé. Les erreurs réseau (fetch du netplay)
  ne déclenchent pas ce bandeau.

## Base de données

SQLite (`state/catalog.db`), deux tables :

- `systems(id, label, core, extensions, position)` — les consoles supportées ;
- `games(system, file, title, region, year, size, mtime, cover, cover_source, match_name, updated_at)`
  — une ligne par ROM présente sur le disque, avec la jaquette associée.

Le disque reste la source de vérité : à chaque appel de `/api/library`, le serveur rescane les dossiers
et synchronise la base (ajout/mise à jour/suppression). Les jaquettes déjà téléchargées sont conservées.
`roms/library.json` permet de forcer un titre, une année ou une jaquette :

```json
{ "snes/mon-jeu.sfc": { "title": "Mon Super Jeu", "year": 1994, "cover": "/roms/snes/covers/mon-jeu.png" } }
```

## Ajouter des jeux

1. **Page web** : `https://retro.kirbytrim.buzz/upload.html` (jeton = `UPLOAD_TOKEN`) — la jaquette
   du jeu est récupérée automatiquement juste après l'envoi.
2. **SFTP** dans `roms/<console>/`, puis sur la page *Ajouter une ROM* → *Récupérer les jaquettes*.
3. Jaquette manuelle : `roms/<console>/covers/<nom-de-la-rom>.png` (prioritaire si la base est vide).

## Dépannage

| Symptôme | Cause probable |
|---|---|
| Page noire, `loader.js 404` | bundle absent → `bash scripts/fetch-ejs.sh /srv/docker/retro/ejs` |
| `Network Error` dans l'émulateur | nom de ROM avec espaces/accents mal résolu, ou core manquant |
| Upload : `Jeton invalide` | `UPLOAD_TOKEN` du `.env` ≠ jeton saisi, puis `docker compose up -d` |
| Jaquette absente | nom de ROM trop exotique → renomme-la comme la base libretro, ou `--all` |
| Lenteur | vérifier le panneau *Diagnostic* du lecteur : mode multi-thread + WebGL matériel |
| PS1 qui ne démarre pas | déposer un BIOS dans `roms/psx/bios/` (`scph1001.bin`…) |

## Licences

Le code du site et du launcher est sous licence **MIT** (voir `LICENSE`). EmulatorJS (GPLv3),
cores RetroArch, jaquettes libretro-thumbnails — voir `/licenses.html`.
**Aucune ROM commerciale n'est fournie par ce dépôt.**
