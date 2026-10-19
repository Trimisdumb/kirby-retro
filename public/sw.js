// Service worker minimal : rend le site installable (PWA).
// Passe-plat volontaire : aucune mise en cache ici (le serveur gère ETag et
// Cache-Control, et le contenu change souvent) — un gestionnaire fetch vide
// suffit pour l'installation sur l'écran d'accueil.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
