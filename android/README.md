# Kirby Retro mobile — application Android (aperçu)

Petite application **WebView** qui ouvre la page mobile du site
(<https://retro.kirbytrim.buzz/mobile.html>) en plein écran : bibliothèque,
manette tactile d'EmulatorJS, écran maintenu allumé, plein écran vidéo.

Aucun code du site n'est dupliqué ici : l'appli charge la page en ligne,
les corrections du site profitent donc directement à l'application.

## Construire l'APK

- **En ligne** : onglet *Actions* → « Application Android (aperçu) » → *Run workflow*.
  L'APK est récupérable dans les artefacts du run.
- **En local** (avec un kit Android) :

  ```sh
  cd android
  gradle assembleDebug
  # → app/build/outputs/apk/debug/app-debug.apk
  ```

L'APK de test est signé avec la clé de debug (installation par sideload,
« sources inconnues » à autoriser). Version : 0.1 — aperçu.
