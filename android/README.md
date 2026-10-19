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

1. Installer **RetroArch officiel (AArch64)** — l'APK de
   [buildbot.libretro.com](https://buildbot.libretro.com/stable/1.22.2/android/RetroArch_aarch64.apk).
   *Pas* celui du Play Store : « RetroArch Plus » n'a accès qu'à son propre dossier
   et ne peut pas lire `KirbyRetroROMs/` — le jeu resterait sur un écran noir.
   Ouvrir RetroArch une fois depuis son icône et accepter l'accès aux fichiers :
   RetroArch ne le demande qu'à ce moment-là, pas quand une ROM arrive d'un
   launcher.
2. Installer l'APK de Kirby Retro (« sources inconnues » à autoriser) — signé en debug.
3. Au premier lancement, autoriser **l'accès aux fichiers** (Android 11+ : *Tous les
   fichiers*), pour que les ROMs soient écrites dans le dossier partagé.

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
  de RetroArch, avec les extras `ROM` et `LIBRETRO` (chemin du core) — c'est la façon
  officieuse utilisée par les frontends Android. L'extra `CONFIGFILE` est volontairement
  omis : il marque un lancement « venu d'un launcher », et RetroArch saute alors sa
  demande d'accès aux fichiers (écran noir si l'accès manque).
- Avant de lancer, l'appli vérifie que le RetroArch installé peut lire le stockage
  partagé — permission « tous les fichiers » (builds récents) ou stockage « hérité »
  des applis qui ciblent Android 10 (les 1.22 officielles) ; sinon elle propose l'APK
  officiel au lieu d'ouvrir un jeu noir. Elle rappelle aussi d'ouvrir RetroArch une
  fois si l'autorisation d'accès aux fichiers n'a jamais été accordée, et les boutons
  « Ouvrir RetroArch » passent bien par son menu (le seul endroit où il demande ce droit).
- Les cores sont demandés par diffusion (`com.retroarch.QUERY_INSTALLED_CORES`),
  ce qui évite de deviner les chemins dans les données privées de RetroArch.

## Limites (aperçu 0.4)

- Pas de sauvegardes synchronisées entre PC et téléphone : RetroArch gère les
  siennes sur le téléphone (le launcher PC continue de synchroniser sur PC).
- Pas de netplay depuis l'appli (l'interface de RetroArch reste dispo pour ça).
- L'APK est signé en debug.
- « RetroArch Plus » du Play Store ne peut pas lire les ROMs hors de son propre
  dossier : utiliser l'APK officiel (l'appli le rappelle avant de lancer).
