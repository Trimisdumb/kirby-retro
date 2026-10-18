// Bibliothèque : catalogue /api/library, filtres, recherche, tri, jeux récents.

const RECENT_KEY = "retro-recent";
const RECENT_MAX = 12;

const state = { library: null, system: "all", query: "", sort: "default" };

const els = {
  chips: document.getElementById("chips"),
  content: document.getElementById("content"),
  skeleton: document.getElementById("skeleton"),
  stats: document.getElementById("stats"),
  empty: document.getElementById("empty"),
  search: document.getElementById("search"),
  footStats: document.getElementById("foot-stats"),
  hero: document.getElementById("hero"),
  heroMeta: document.getElementById("hero-meta"),
  recent: document.getElementById("recent"),
  recentList: document.getElementById("recent-list"),
  recentCount: document.getElementById("recent-count"),
  sort: document.getElementById("sort"),
};

const REGION_LABELS = {
  EUR: "Europe", USA: "USA", JAP: "Japon", WLD: "Monde", FRA: "France", GER: "Allemagne",
  SPA: "Espagne", ITA: "Italie", NLD: "Pays-Bas", SWE: "Suède", KOR: "Corée", CHN: "Chine",
  AUS: "Australie", CAN: "Canada", BRA: "Brésil",
};

const formatSize = (bytes) => {
  if (!bytes) return "";
  const units = ["o", "Ko", "Mo", "Go"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 || value >= 10 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
};

const storageOk = (() => {
  try {
    localStorage.setItem("retro-probe", "1");
    localStorage.removeItem("retro-probe");
    return true;
  } catch {
    return false;
  }
})();

function loadRecent() {
  if (!storageOk) return [];
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function playUrl(system, file) {
  return `/play.html?system=${encodeURIComponent(system)}&file=${encodeURIComponent(file)}`;
}

function launcherUrl(system, file) {
  return `kirbyretro://play?system=${encodeURIComponent(system)}&file=${encodeURIComponent(file)}`;
}

/** Consoles mieux adaptées au launcher natif (WASM trop lourd). */
const LAUNCHER_PREFERRED = new Set(["nds", "n64", "psx", "psp"]);

/** Bandeau de secours quand le lien kirbyretro:// ne s'ouvre pas
 *  (launcher non installé, Firefox sans autorisation, etc.).
 *  fallbackHref = null → console sans émulateur navigateur : pas de bouton « navigateur ». */
function showLauncherToast(title, fallbackHref) {
  document.querySelector(".flash-toast")?.remove();
  const toast = document.createElement("div");
  toast.className = "flash-toast";
  toast.setAttribute("role", "status");

  const text = document.createElement("span");
  text.className = "flash-text";
  const strong = document.createElement("strong");
  strong.textContent = title;
  text.append(strong, document.createTextNode(" — ouverture dans le launcher natif…"));

  const install = document.createElement("a");
  install.className = "btn ghost sm";
  install.href = "/client.html";
  install.textContent = "⬇ Installer le launcher";

  const close = document.createElement("button");
  close.type = "button";
  close.className = "flash-close";
  close.setAttribute("aria-label", "Fermer");
  close.textContent = "✕";
  close.addEventListener("click", () => toast.remove());

  if (fallbackHref) {
    const browser = document.createElement("a");
    browser.className = "btn sm";
    browser.href = fallbackHref;
    browser.textContent = "▶ Jouer dans le navigateur";
    toast.append(text, browser, install, close);
  } else {
    const note = document.createElement("span");
    note.className = "flash-text";
    note.textContent = "🔒 Cette console ne tourne pas dans le navigateur — il faut le launcher + RetroArch.";
    toast.append(text, note, install, close);
  }
  document.body.append(toast);
  window.clearTimeout(showLauncherToast._timer);
  showLauncherToast._timer = window.setTimeout(() => toast.remove(), 15000);
}


function buildSkeleton(count = 12) {
  els.skeleton.replaceChildren(
    ...Array.from({ length: count }, () => {
      const card = document.createElement("div");
      card.className = "card ghost-card";
      card.innerHTML = '<div class="cover"></div><div class="meta"><span></span><span></span></div>';
      return card;
    }),
  );
}

function placeholder(game) {
  const box = document.createElement("span");
  box.className = "placeholder-inner";
  const label = String(game.label || game.system || "?");
  const short = label.split(/[\s/]+/u).map((word) => word[0]).join("").slice(0, 3).toUpperCase();
  box.innerHTML = `<em>${short}</em><i>${(game.title || "?").slice(0, 1).toUpperCase()}</i>`;
  return box;
}

function card(game) {
  const link = document.createElement("a");
  link.className = "card";
  const system = (state.library?.systems ?? []).find((entry) => entry.id === game.system);
  // Console sans émulateur navigateur (core vide) → toujours via le launcher natif.
  const nativeOnly = Boolean(system && !system.core);
  const preferLauncher = nativeOnly || LAUNCHER_PREFERRED.has(game.system);
  link.href = preferLauncher ? launcherUrl(game.system, game.file) : playUrl(game.system, game.file);
  link.title = nativeOnly
    ? `${game.title} — console jouable uniquement via le launcher natif (RetroArch)`
    : preferLauncher
      ? `${game.title} — ouvrir dans le launcher natif (recommandé)`
      : game.title;
  if (preferLauncher) {
    link.addEventListener("click", () => {
      // Le protocole kirbyretro:// peut ne pas être géré (launcher non installé,
      // Firefox sans autorisation…) : bandeau de secours discret, jamais bloquant.
      const fallback = nativeOnly ? null : playUrl(game.system, game.file);
      window.setTimeout(() => showLauncherToast(game.title || game.file, fallback), 1200);
    });
  }

  const cover = document.createElement("div");
  cover.className = "cover";
  if (game.cover) {
    const image = document.createElement("img");
    image.src = game.cover;
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    image.addEventListener("error", () => {
      image.remove();
      cover.classList.add("placeholder");
      cover.append(placeholder(game));
    });
    cover.append(image);
  } else {
    cover.classList.add("placeholder");
    cover.append(placeholder(game));
  }

  const play = document.createElement("span");
  play.className = "play";
  play.setAttribute("aria-hidden", "true");
  cover.append(play);

  const meta = document.createElement("div");
  meta.className = "meta";
  const title = document.createElement("h3");
  title.textContent = game.title;
  const sub = document.createElement("p");
  const bits = [];
  if (game.region) {
    const badge = document.createElement("span");
    badge.className = "region";
    badge.textContent = game.region;
    badge.title = REGION_LABELS[game.region] || game.region;
    bits.push(badge);
  }
  const rest = document.createElement("span");
  rest.textContent = [game.year || null, formatSize(game.size)].filter(Boolean).join(" · ");
  if (rest.textContent) bits.push(rest);
  if (nativeOnly) {
    const nativeBadge = document.createElement("span");
    nativeBadge.className = "native-badge";
    nativeBadge.textContent = "🖥 launcher";
    nativeBadge.title = "Console jouable uniquement via le launcher natif (RetroArch)";
    bits.push(nativeBadge);
  }
  sub.append(...bits);
  meta.append(title, sub);

  link.append(cover, meta);
  return link;
}

function sortGames(games) {
  const list = games.slice();
  switch (state.sort) {
    case "title":
      list.sort((a, b) => a.title.localeCompare(b.title, "fr", { sensitivity: "base" }));
      break;
    case "title-desc":
      list.sort((a, b) => b.title.localeCompare(a.title, "fr", { sensitivity: "base" }));
      break;
    case "year":
      list.sort((a, b) => (Number(b.year) || 0) - (Number(a.year) || 0) || a.title.localeCompare(b.title, "fr"));
      break;
    case "size":
      list.sort((a, b) => (b.size || 0) - (a.size || 0));
      break;
    default:
      break;
  }
  return list;
}

function grid(games) {
  const container = document.createElement("div");
  container.className = "grid";
  container.append(...sortGames(games).map(card));
  return container;
}

function section(system, games) {
  const wrapper = document.createElement("section");
  wrapper.className = "shelf";
  const header = document.createElement("div");
  header.className = "shelf-head";
  const title = document.createElement("h2");
  title.textContent = system.label;
  const count = document.createElement("span");
  count.className = "count";
  count.textContent = `${games.length} jeu${games.length > 1 ? "x" : ""}`;
  header.append(title, count);
  wrapper.append(header, grid(games));
  return wrapper;
}

function chips() {
  const systems = (state.library?.systems ?? []).filter((system) => system.count > 0);
  const total = systems.reduce((sum, system) => sum + system.count, 0);
  const items = [{ id: "all", label: "Tout", count: total }, ...systems];
  els.chips.replaceChildren(
    ...items.map((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `chip${state.system === item.id ? " active" : ""}`;
      button.innerHTML = `${item.label}<span>${item.count}</span>`;
      button.addEventListener("click", () => {
        state.system = item.id;
        chips();
        render();
      });
      return button;
    }),
  );
}

function paintHero() {
  if (!state.library) return;
  const systems = (state.library.systems ?? []).filter((s) => s.count > 0);
  const total = state.library.totalGames || 0;
  els.hero.hidden = total === 0;
  if (total === 0) return;
  els.heroMeta.replaceChildren(
    ...[
      ["Jeux", String(total)],
      ["Consoles", String(systems.length)],
      state.library.covers
        ? ["Jaquettes", `${state.library.covers.withCover}`]
        : null,
    ]
      .filter(Boolean)
      .map(([label, value]) => {
        const span = document.createElement("span");
        span.className = "hero-stat";
        span.innerHTML = `<strong>${value}</strong> ${label}`;
        return span;
      }),
  );
}

function paintRecent() {
  const recent = loadRecent();
  if (!recent.length || !state.library) {
    els.recent.hidden = true;
    return;
  }
  const byKey = new Map();
  for (const system of state.library.systems ?? []) {
    for (const game of system.games) {
      byKey.set(`${game.system}/${game.file}`, { ...game, label: system.label });
    }
  }
  const resolved = [];
  for (const entry of recent) {
    const game = byKey.get(`${entry.system}/${entry.file}`);
    if (game) resolved.push(game);
  }
  if (!resolved.length) {
    els.recent.hidden = true;
    return;
  }
  els.recent.hidden = false;
  els.recentCount.textContent = `${resolved.length}`;
  els.recentList.replaceChildren(...resolved.map(card));
}

/** Minuscules sans accents, pour une recherche tolérante (« pokemon » trouve « Pokémon »). */
function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/gu, "");
}

function render() {
  if (!state.library) return;
  const query = normalizeText(state.query.trim());
  const systems = (state.library.systems ?? [])
    .filter((system) => state.system === "all" || system.id === state.system)
    .map((system) => {
      const games = system.games
        .map((game) => ({ ...game, label: system.label }))
        .filter(
          (game) =>
            !query ||
            normalizeText(game.title).includes(query) ||
            normalizeText(game.file).includes(query) ||
            normalizeText(game.region).includes(query) ||
            normalizeText(game.label).includes(query),
        );
      return { ...system, games };
    });

  const shown = systems.reduce((sum, system) => sum + system.games.length, 0);
  const total = state.library.totalGames;

  if (!shown) {
    els.content.replaceChildren();
    els.empty.hidden = false;
    els.stats.textContent = total === 0 ? "Bibliothèque vide" : `Aucun résultat pour « ${state.query} »`;
    return;
  }

  els.empty.hidden = true;
  const filtered = state.system !== "all" || query || state.sort !== "default";
  const visibleSystems = systems.filter((system) => system.games.length);
  els.content.replaceChildren(
    ...(filtered
      ? [grid(systems.flatMap((system) => system.games))]
      : visibleSystems.map((system) => section(system, system.games))),
  );

  els.stats.innerHTML = filtered
    ? `<strong>${shown}</strong> jeu${shown > 1 ? "x" : ""} affiché${shown > 1 ? "s" : ""} sur ${total}`
    : `<strong>${total}</strong> jeu${total > 1 ? "x" : ""} prêt${total > 1 ? "s" : ""} à jouer · ${visibleSystems.length} console${visibleSystems.length > 1 ? "s" : ""}`;
}

async function boot() {
  buildSkeleton();
  try {
    const response = await fetch("/api/library");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.library = await response.json();
  } catch (error) {
    els.skeleton.remove();
    els.stats.textContent = `Impossible de charger la bibliothèque (${error.message}).`;
    return;
  }

  els.skeleton.remove();
  const covers = state.library.covers;
  if (covers) {
    els.footStats.textContent = `${covers.withCover} jaquette(s) · ${covers.withoutCover} sans image`;
  }

  if (state.library.totalGames > 0) {
    els.sort.hidden = false;
  }

  paintHero();
  paintRecent();
  chips();
  render();
}

els.search.addEventListener("input", (event) => {
  state.query = event.target.value;
  render();
});

els.sort?.addEventListener("change", (event) => {
  state.sort = event.target.value;
  render();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== els.search && !event.metaKey && !event.ctrlKey) {
    event.preventDefault();
    els.search.focus();
  }
  if (event.key === "Escape" && document.activeElement === els.search) {
    els.search.value = "";
    state.query = "";
    els.search.blur();
    render();
  }
});

boot();
