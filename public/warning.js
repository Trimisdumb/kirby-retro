/* Avertissement légal — affiché à la première visite (mémorisé par navigateur).
   Rouvrable à tout moment : window.avertissementLegal() ou lien « Informations légales ». */
(function () {
  "use strict";
  var KEY = "kirbyretro-avertissement-vu";
  var CSS = [
    ".avertissement-overlay{position:fixed;inset:0;background:#0f2233cc;display:flex;align-items:center;justify-content:center;padding:1rem;z-index:9999}",
    ".avertissement-boite{background:#fff;color:#23394a;box-sizing:border-box;width:100%;max-width:46rem;max-height:86vh;overflow:auto;border-radius:16px;padding:1.4rem 1.6rem;box-shadow:0 18px 50px #0008;line-height:1.6}",
    ".avertissement-boite h2{margin:0 0 .6rem;color:var(--wii-blue-deep,#2b7eb0);font-size:1.25rem}",
    ".avertissement-boite h3{margin:1.1rem 0 .35rem;color:var(--wii-blue-deep,#2b7eb0);font-size:1.02rem}",
    ".avertissement-boite p{margin:.45rem 0}",
    ".avertissement-pied{margin-top:1.2rem;text-align:right}",
    ".avertissement-pied button{background:var(--wii-blue,#3a9fd8);color:#fff;border:none;border-radius:999px;padding:.55rem 1.4rem;font-size:1rem;font-weight:600;cursor:pointer;font-family:inherit}",
    ".avertissement-pied button:hover{background:var(--wii-blue-deep,#2b7eb0)}",
    ".avertissement-mail{font-weight:700}",
    "@media (max-width:520px){.avertissement-overlay{padding:.6rem}.avertissement-boite{padding:1rem 1rem .9rem}.avertissement-boite h2{font-size:1.1rem}}",
  ].join("");
  var CONTENU = [
    "<h3>À propos du projet</h3>",
    "<p>Ce site est un projet personnel consacré aux jeux vidéo rétro, développé par passion et initialement destiné à permettre à mes amis et à moi-même de jouer ensemble.</p>",
    "<p>Le site est entièrement gratuit, ne génère aucun revenu et n'a aucun objectif commercial. Il a été créé uniquement pour le plaisir et pour partager ma passion du jeu rétro.</p>",
    "<h3>Concernant les jeux et les fichiers</h3>",
    "<p>Les jeux proposés sur ce site sont liés à des consoles physiques que je possède. Toutefois, la possession d'une console ou d'un jeu original ne confère pas automatiquement le droit de reproduire, d'héberger ou de distribuer les fichiers correspondants.</p>",
    "<p>Je ne souhaite ni encourager le piratage ni porter atteinte aux droits des développeurs, éditeurs ou autres ayants droit. Le caractère personnel et non lucratif de ce projet ne garantit pas, à lui seul, la légalité des contenus mis à disposition.</p>",
    "<p>Merci de ne pas redistribuer les fichiers hébergés sur ce site ni de les republier sur d'autres plateformes sans autorisation appropriée.</p>",
    "<h3>Demandes des ayants droit</h3>",
    "<p>Si Nintendo ou tout autre ayant droit estime qu'un contenu présent sur ce site porte atteinte à ses droits, il peut me contacter afin que je puisse examiner sa demande.</p>",
    "<p>Je prendrai toute demande sérieuse en considération et agirai en conséquence, notamment en retirant le contenu concerné ou, si nécessaire, en fermant le site.</p>",
    "<h3>Contact</h3>",
    "<p>Pour toute demande sérieuse concernant les droits d'auteur ou le contenu du site :</p>",
    "<p class=\"avertissement-mail\"><a href=\"mailto:thetrimmmmmm@gmail.com\">thetrimmmmmm@gmail.com</a></p>",
    "<p>Merci de réserver cette adresse aux demandes pertinentes et de ne pas m'envoyer de messages sans motif valable.</p>",
    "<p>Ce projet est avant tout une initiative personnelle créée par passion pour le jeu rétro, sans but lucratif et sans volonté de nuire aux ayants droit.</p>",
    "<p><strong>Merci à tous ceux qui comprennent et respectent l'esprit de ce projet ! ❤️</strong></p>",
  ].join("");

  function fermer(overlay) {
    overlay.remove();
    try { localStorage.setItem(KEY, "1"); } catch (e) { /* stockage indisponible */ }
  }

  function afficher() {
    if (document.getElementById("avertissement")) return;
    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);
    var overlay = document.createElement("div");
    overlay.id = "avertissement";
    overlay.className = "avertissement-overlay";
    overlay.innerHTML =
      '<div class="avertissement-boite" role="dialog" aria-modal="true" aria-labelledby="avertissement-titre">' +
      '<h2 id="avertissement-titre">⚠️ Informations légales et avertissement</h2>' +
      CONTENU +
      '<div class="avertissement-pied"><button type="button">J\'ai compris</button></div>' +
      "</div>";
    document.body.appendChild(overlay);
    overlay.querySelector("button").addEventListener("click", function () { fermer(overlay); });
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) fermer(overlay);
    });
  }

  window.avertissementLegal = afficher;

  function premierVisite() {
    var vu = false;
    try { vu = localStorage.getItem(KEY) === "1"; } catch (e) { /* stockage indisponible */ }
    if (!vu) afficher();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", premierVisite);
  } else {
    premierVisite();
  }
})();
