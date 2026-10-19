# Kirby Retro mobile — application Android (aperçu)

La même idée que le launcher PC, dans le téléphone :

- **bibliothèque** du site (mêmes jaquettes, même recherche, mêmes filtres par console) ;
- **téléchargement des ROMs** dans `KirbyRetroROMs/` à la racine du stockage
  (le dossier du launcher PC, transposé au téléphone) ;
- **lancement direct dans RetroArch** : l'appli impose le core de la console
  (comme sur PC), en ne choisissant que parmi les cores réellement installés —
  RetroArch sait énumérer ses cores, l'appli l'interroge au démarrage ;
- si aucun core conseillé n'est installé, la première lecture propose la liste
  des cores présents (choix retenu pour cette console, oubliable dans Paramètres) ;
- **« Ouvrir avec… »** pour lancer la ROM dans une autre appli (Lemuroid, PPSSPP…).

## Installer

1. Installer **RetroArch** (ou RetroArch Plus) depuis le Play Store, si ce n'est pas déjà fait.
2. Installer l'APK de Kirby Retro (« sources inconnues » à autoriser) — signé en debug.
3. Au premier lancement, autoriser **l'accès aux fichiers** (Android 11+ : *Tous les
   fichiers*), pour que les ROMs soient visibles par RetroArch.

## Construire l'APK

- **En ligne** : onglet *Actions* → « Application Android (aperçu) » → *Run workflow*.
  L'APK est récupérable dans les artefacts du run.
- **En local** (avec un kit Android) :

  ```sh
  cd android
  gradle assembleDebug
  # → app/build/outputs/apk/debug/app-debug.apk
  ```

## Comment ça marche

- Le catalogue vient de `GET /api/library` sur le site (adresse modifiable dans
  Paramètres) ; la dernière réponse est gardée en cache pour démarrer hors ligne.
- Le lancement passe par l'activité `com.retroarch.browser.retroactivity.RetroActivityFuture`
  de RetroArch, avec les extras `ROM`, `LIBRETRO` (chemin du core) et `CONFIGFILE` —
  c'est la façon officieuse utilisée par les frontends Android.
- Les cores sont demandés par diffusion (`com.retroarch.QUERY_INSTALLED_CORES`),
  ce qui évite de deviner les chemins dans les données privées de RetroArch.

## Limites (aperçu 0.2)

- Pas de sauvegardes synchronisées entre PC et téléphone : RetroArch gère les
  siennes sur le téléphone (le launcher PC continue de synchroniser sur PC).
- Pas de netplay depuis l'appli (l'interface de RetroArch reste dispo pour ça).
- L'APK est signé en debug.
