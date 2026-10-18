#!/usr/bin/env node
/**
 * retro.kirbytrim.buzz — bibliothèque de ROMs + émulateurs WASM (EmulatorJS auto-hébergé).
 *
 * Serveur HTTP sans aucune dépendance externe : node:http + node:fs + node:sqlite.
 *   /                    → bibliothèque (public/)
 *   /play.html           → lecteur EmulatorJS
 *   /ejs/data/*          → bundle EmulatorJS (loader, cores, localisation)
 *   /roms/<console>/*    → ROMs (bind mount, lecture + upload)
 *   /covers/<console>/*  → jaquettes récupérées automatiquement
 *   /api/library         → catalogue (SQLite) au format JSON
 *   /api/covers/refresh  → relance la récupération des jaquettes (jeton requis)
 *   /api/upload          → dépôt d'une ROM (jeton requis ; par morceaux : ?offset= &done=1)
 *   /healthz             → sonde Docker
 */
import { createServer } from "node:http";
import { createReadStream, createWriteStream } from "node:fs";
import { createGzip, constants as zlibConstants } from "node:zlib";
import { mkdir, readdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { once } from "node:events";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { timingSafeEqual } from "node:crypto";

import { openCatalog } from "./catalog.mjs";
import { fetchMissingCovers, LIBRETRO_SYSTEMS, parseRomName } from "./covers.mjs";

const HERE = fileURLToPath(new URL("..", import.meta.url));
const PORT = Number(process.env.PORT || 8090);
const HOST = process.env.HOST || "0.0.0.0";
const PUBLIC_DIR = resolve(process.env.PUBLIC_DIR || join(HERE, "public"));
const EJS_DIR = resolve(process.env.EJS_DIR || "/data/ejs");
const ROMS_DIR = resolve(process.env.ROMS_DIR || "/data/roms");
const COVERS_DIR = resolve(process.env.COVERS_DIR || "/data/covers");
const STATE_DIR = resolve(process.env.STATE_DIR || "/data/state");
const CATALOG_DB = process.env.CATALOG_DB || join(STATE_DIR, "catalog.db");
const INDEX_CACHE_DIR = process.env.INDEX_CACHE_DIR || join(STATE_DIR, "libretro-index");
const UPLOAD_TOKEN = (process.env.UPLOAD_TOKEN || "").trim();
const MAX_UPLOAD_MB = Number(process.env.MAX_UPLOAD_MB || 512);
/** Taille max d'un morceau d'upload par morceaux (marge sous la limite Cloudflare de 100 Mo). */
const CHUNK_MAX_MB = 96;
const SITE_NAME = process.env.SITE_NAME || "Retro";

/** Console → core EmulatorJS par défaut + extensions acceptées. */
const SYSTEMS = [
  { id: "nes", label: "NES / Famicom", core: "fceumm", ext: ["nes", "fds", "unf", "unif", "zip"] },
  { id: "snes", label: "Super Nintendo", core: "snes9x", ext: ["smc", "sfc", "swc", "fig", "zip"] },
  { id: "gb", label: "Game Boy / Color", core: "gambatte", ext: ["gb", "gbc", "dmg", "zip"] },
  { id: "gba", label: "Game Boy Advance", core: "mgba", ext: ["gba", "agb", "zip"] },
  { id: "n64", label: "Nintendo 64", core: "mupen64plus_next", ext: ["n64", "z64", "v64", "u1", "ndd", "zip"] },
  { id: "nds", label: "Nintendo DS", core: "melonds", ext: ["nds", "zip"] },
  { id: "psx", label: "PlayStation", core: "pcsx_rearmed", ext: ["cue", "chd", "pbp", "iso", "img", "mdf", "bin"] },
  { id: "segaMD", label: "Mega Drive / Genesis", core: "genesis_plus_gx", ext: ["md", "gen", "smd", "bin", "zip"] },
  { id: "segaMS", label: "Master System", core: "smsplus", ext: ["sms", "zip"] },
  { id: "segaGG", label: "Game Gear", core: "genesis_plus_gx", ext: ["gg", "zip"] },
  { id: "pce", label: "PC Engine / TurboGrafx", core: "mednafen_pce", ext: ["pce", "sgx", "zip"] },
  { id: "atari2600", label: "Atari 2600", core: "stella2014", ext: ["a26", "bin"] },
  { id: "lynx", label: "Atari Lynx", core: "handy", ext: ["lnx", "zip"] },
  { id: "c64", label: "Commodore 64", core: "vice_x64sc", ext: ["d64", "t64", "prg", "tap", "crt", "nib", "zip"] },
  { id: "vb", label: "Virtual Boy", core: "beetle_vb", ext: ["vb", "vboy", "zip"] },
  // Ajouts v1.3.0 — consoles couvertes par les cores RetroArch
  { id: "sega32x", label: "Sega 32X", core: "picodrive", ext: ["32x", "bin", "zip"] },
  { id: "segaSaturn", label: "Sega Saturn", core: "", ext: ["cue", "chd", "bin", "iso", "img", "mdf"] },
  { id: "dreamcast", label: "Dreamcast", core: "", ext: ["cdi", "gdi", "chd", "cue", "bin", "iso", "dat"] },
  { id: "arcade", label: "Arcade (FBNeo)", core: "fbneo", ext: ["zip"] },
  { id: "psp", label: "PlayStation Portable", core: "ppsspp", ext: ["iso", "cso", "chd"] },
  { id: "gamecube", label: "GameCube", core: "", ext: ["iso", "rvz", "gcz", "ciso", "wia", "gcm"] },
  { id: "wii", label: "Wii", core: "", ext: ["iso", "rvz", "wbfs", "wia"] },
  { id: "ps2", label: "PlayStation 2", core: "", ext: ["iso", "chd", "cso", "gz"] },
  { id: "3ds", label: "Nintendo 3DS", core: "", ext: ["3ds", "cci", "cia", "3dsx"] },
  { id: "cpc", label: "Amstrad CPC", core: "", ext: ["dsk", "cdt", "sna", "tap", "zip"] },
  { id: "apple2", label: "Apple II", core: "", ext: ["dsk", "do", "po", "nib", "woz", "zip"] },
  { id: "pc88", label: "NEC PC-88", core: "", ext: ["d88", "m3u", "zip"] },
  { id: "pokemini", label: "Pokémon Mini", core: "", ext: ["min", "zip"] },
];
const SYSTEM_BY_ID = new Map(SYSTEMS.map((system) => [system.id, system]));
const CATALOG = openCatalog(CATALOG_DB);
CATALOG.saveSystems(SYSTEMS);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".wasm": "application/wasm",
  ".data": "application/octet-stream",
  ".zip": "application/zip",
  ".txt": "text/plain; charset=utf-8",
  ".md": "text/plain; charset=utf-8",
};

const mimeFor = (file) => MIME[extname(file).toLowerCase()] || "application/octet-stream";

/**
 * Isolation cross-origin : indispensable pour exposer SharedArrayBuffer, donc pour
 * que les cores multi-thread (EJS_threads) puissent tourner — gros gain de performance
 * sur N64 / NDS / PS1. Tout le site est same-origin, donc COEP ne casse rien.
 */
const ISOLATION_HEADERS = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
  "Cross-Origin-Resource-Policy": "same-origin",
};

function send(res, status, body, headers = {}) {
  const payload = Buffer.isBuffer(body) ? body : Buffer.from(String(body ?? ""), "utf8");
  res.writeHead(status, {
    ...ISOLATION_HEADERS,
    "Content-Type": "text/plain; charset=utf-8",
    "Content-Length": String(payload.length),
    "Cache-Control": "no-store",
    ...headers,
  });
  res.end(payload);
}

function sendJson(res, status, value) {
  send(res, status, JSON.stringify(value), {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
}

/** Empêche toute remontée de répertoire (../). Renvoie null si la cible sort de la racine. */
function safeJoin(base, relative) {
  let decoded = String(relative);
  try {
    // Les noms de ROM contiennent souvent des espaces/parenthèses : %20 → " ", etc.
    decoded = decodeURIComponent(decoded);
  } catch {
    // séquence % invalide : on garde la valeur brute
  }
  if (decoded.includes("\0")) return null;
  const clean = normalize(decoded).replace(/^([/\\])+/, "");
  const target = resolve(base, clean);
  if (target !== base && !target.startsWith(base + sep)) return null;
  return target;
}

/** Extensions textuelles compressibles (gzip) — pas les ROMs ni les .wasm déjà compressés. */
const GZIP_EXTS = new Set([".html", ".js", ".mjs", ".css", ".json", ".svg", ".txt", ".xml", ".map"]);

async function sendFile(req, res, filePath, { immutable = false, maxAge = 300 } = {}) {
  if (!filePath) return send(res, 404, "Introuvable.");
  const info = await stat(filePath).catch(() => null);
  if (!info || !info.isFile()) return send(res, 404, "Introuvable.");

  const etag = `"${info.size.toString(16)}-${Math.floor(info.mtimeMs).toString(16)}"`;
  const extension = extname(filePath).toLowerCase();
  const headers = {
    ...ISOLATION_HEADERS,
    "Content-Type": mimeFor(filePath),
    "Last-Modified": new Date(info.mtimeMs).toUTCString(),
    ETag: etag,
    "Accept-Ranges": "bytes",
    // Le HTML doit toujours être revalidé (sinon Cloudflare sert une vieille page) ;
    // ROMs, cores et jaquettes restent cachables.
    "Cache-Control": immutable
      ? "public, max-age=31536000, immutable"
      : extension === ".html"
        ? "public, max-age=0, must-revalidate"
        : extension === ".js" || extension === ".css"
          ? `public, max-age=${Math.max(maxAge, 3600)}`
          : `public, max-age=${maxAge}`,
  };

  if (!immutable && req.headers["if-none-match"] === etag) {
    res.writeHead(304, headers);
    return res.end();
  }

  let start = 0;
  let end = info.size - 1;
  let status = 200;
  const range = req.headers.range;
  if (range) {
    const match = /^bytes=(\d*)-(\d*)$/u.exec(range.trim());
    if (match && (match[1] || match[2])) {
      if (match[1]) {
        start = Number(match[1]);
        end = match[2] ? Number(match[2]) : info.size - 1;
      } else {
        start = Math.max(0, info.size - Number(match[2]));
        end = info.size - 1;
      }
      if (Number.isNaN(start) || Number.isNaN(end) || start > end || start >= info.size) {
        res.writeHead(416, { "Content-Range": `bytes */${info.size}` });
        return res.end();
      }
      status = 206;
      headers["Content-Range"] = `bytes ${start}-${end}/${info.size}`;
    }
  }

  // Gzip pour les assets texte (hors range requests et hors fichiers déjà binaires).
  const acceptEncoding = String(req.headers["accept-encoding"] || "");
  const canGzip =
    status === 200 &&
    !range &&
    GZIP_EXTS.has(extension) &&
    info.size > 1024 &&
    /\bgzip\b/i.test(acceptEncoding);

  if (canGzip) {
    headers["Content-Encoding"] = "gzip";
    headers["Vary"] = "Accept-Encoding";
    delete headers["Content-Length"]; // taille après compression inconnue
    res.writeHead(status, headers);
    if (req.method === "HEAD") return res.end();
    const stream = createReadStream(filePath);
    const gzip = createGzip({ level: zlibConstants.Z_BEST_SPEED });
    stream.on("error", () => res.destroy());
    gzip.on("error", () => res.destroy());
    stream.pipe(gzip).pipe(res);
    return;
  }

  headers["Content-Length"] = String(end - start + 1);
  res.writeHead(status, headers);
  if (req.method === "HEAD") return res.end();
  const stream = createReadStream(filePath, { start, end });
  stream.on("error", () => res.destroy());
  stream.pipe(res);
}

/* ------------------------------------------------------------------ catalogue */

async function readLibraryMeta() {
  const raw = await readFile(join(ROMS_DIR, "library.json"), "utf8").catch(() => "{}");
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    console.warn("[retro] roms/library.json illisible, métadonnées ignorées");
    return {};
  }
}

/** Scanne le disque et met le catalogue SQLite à jour (fichiers ajoutés/retirés). */
async function syncLibrary() {
  const overrides = await readLibraryMeta();
  const rows = [];

  for (const system of SYSTEMS) {
    const dir = join(ROMS_DIR, system.id);
    const entries = await readdir(dir, { withFileTypes: true }).catch(() => []);
    const names = new Set(entries.filter((entry) => entry.isFile()).map((entry) => entry.name));

    for (const entry of entries) {
      if (!entry.isFile() || entry.name.startsWith(".")) continue;
      const ext = extname(entry.name).slice(1).toLowerCase();
      if (!system.ext.includes(ext)) continue;
      // PlayStation : un .cue + un .bin du même nom = un seul jeu (le .cue gagne).
      if (ext === "bin" && names.has(entry.name.replace(/\.bin$/iu, ".cue"))) continue;

      const info = await stat(join(dir, entry.name)).catch(() => null);
      if (!info) continue;

      const parsed = parseRomName(entry.name);
      const override = overrides[`${system.id}/${entry.name}`] || {};
      rows.push({
        system: system.id,
        file: entry.name,
        title: override.title || parsed.title,
        region: override.region || parsed.region,
        year: override.year || parsed.year,
        size: info.size,
        mtime: Math.floor(info.mtimeMs),
      });
    }
  }

  CATALOG.syncGames(rows);
}

/** Catalogue au format attendu par le navigateur. */
async function buildLibrary() {
  await syncLibrary();
  const systems = [];
  let totalGames = 0;

  for (const row of CATALOG.systemsWithCount()) {
    const games = [];
    for (const game of CATALOG.gamesOfSystem(row.id)) {
      const slug = game.file.replace(/\.[^.]+$/u, "");
      let cover = game.cover || null;
      if (!cover) {
        // jaquette déposée à la main : roms/<console>/covers/<nom>.png
        const manual = await stat(join(ROMS_DIR, row.id, "covers", `${slug}.png`)).then(() => true).catch(() => false);
        if (manual) cover = `/roms/${row.id}/covers/${encodeURIComponent(slug)}.png`;
      }
      games.push({
        system: game.system,
        file: game.file,
        title: game.title,
        region: game.region || null,
        year: game.year || null,
        size: game.size,
        cover,
        coverSource: game.cover_source || null,
      });
    }
    totalGames += games.length;
    systems.push({
      id: row.id,
      label: row.label,
      core: row.core,
      extensions: String(row.extensions).split(","),
      hasCoverSource: Boolean(LIBRETRO_SYSTEMS[row.id]),
      count: games.length,
      games,
    });
  }

  return {
    name: SITE_NAME,
    totalGames,
    uploadEnabled: Boolean(UPLOAD_TOKEN),
    maxUploadMb: MAX_UPLOAD_MB,
    covers: coverJobStatus(),
    systems,
  };
}

/* --------------------------------------------------------------- jaquettes */

let coverJob = {
  running: false,
  startedAt: null,
  finishedAt: null,
  total: 0,
  summary: null,
  error: null,
};

function coverJobStatus() {
  return {
    running: coverJob.running,
    startedAt: coverJob.startedAt,
    finishedAt: coverJob.finishedAt,
    total: coverJob.total,
    summary: coverJob.summary,
    error: coverJob.error,
    withCover: CATALOG.allGames().filter((game) => game.cover).length,
    withoutCover: CATALOG.allGames().filter((game) => !game.cover).length,
  };
}

function startCoverJob({ systems = null } = {}) {
  if (coverJob.running) return coverJobStatus();
  coverJob = { running: true, startedAt: Date.now(), finishedAt: null, total: 0, summary: null, error: null };

  (async () => {
    try {
      await syncLibrary();
      let games = CATALOG.gamesMissingCover();
      if (systems?.length) games = games.filter((game) => systems.includes(game.system));
      coverJob.total = games.length;
      if (!games.length) {
        coverJob.summary = { found: 0, missing: 0, systems: 0, message: "aucune jaquette manquante" };
        return;
      }
      coverJob.summary = await fetchMissingCovers({
        games,
        coversDir: COVERS_DIR,
        cacheDir: INDEX_CACHE_DIR,
        onCover: (system, file, info) => CATALOG.setCover(system, file, info),
        log: (message) => console.log(`[covers] ${message}`),
      });
    } catch (error) {
      coverJob.error = error.message;
      console.error("[covers] échec :", error);
    } finally {
      coverJob.running = false;
      coverJob.finishedAt = Date.now();
    }
  })();

  return coverJobStatus();
}

/* ------------------------------------------------------------------ uploads */

function sanitizeUploadName(name) {
  const base = String(name || "").split(/[/\\]/u).pop() || "";
  const safe = base.replace(/[^\w.\- ()[\]]/gu, "_").replace(/^\.+/u, "").trim();
  return safe.slice(0, 160);
}

function tokenMatches(provided) {
  const a = Buffer.from(String(provided || ""));
  const b = Buffer.from(UPLOAD_TOKEN);
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

function providedToken(req) {
  const header = req.headers["x-upload-token"];
  return Array.isArray(header) ? header[0] : header;
}

async function handleUpload(req, res, url) {
  if (req.method !== "POST") return send(res, 405, "Utilise POST pour déposer une ROM.");
  if (!UPLOAD_TOKEN) return send(res, 403, "Dépôt désactivé : renseigne UPLOAD_TOKEN dans le .env.");
  if (!tokenMatches(providedToken(req))) return send(res, 401, "Jeton d'upload invalide.");

  const system = SYSTEM_BY_ID.get(url.searchParams.get("system") || "");
  if (!system) return send(res, 400, "Console inconnue.");

  const fileName = sanitizeUploadName(url.searchParams.get("name"));
  if (!fileName) return send(res, 400, "Nom de fichier manquant.");

  const ext = extname(fileName).slice(1).toLowerCase();
  if (!system.ext.includes(ext)) {
    return send(res, 400, `Extension .${ext} refusée pour ${system.label}.`);
  }

  const dir = join(ROMS_DIR, system.id);
  await mkdir(dir, { recursive: true });
  const destination = join(dir, fileName);
  const temp = `${destination}.part`;

  // Envoi par morceaux (contourne la limite de 100 Mo de Cloudflare) :
  // ?offset=N (octets déjà reçus) puis &done=1 sur le dernier morceau.
  // Sans « offset », on garde l'ancien mode « tout en un » (plafonné à MAX_UPLOAD_MB).
  const chunked = url.searchParams.has("offset");
  const offset = chunked ? Number(url.searchParams.get("offset") || "0") : 0;
  const done = !chunked || url.searchParams.get("done") === "1";
  if (!Number.isInteger(offset) || offset < 0) return send(res, 400, "Offset invalide.");

  if (chunked && offset > 0) {
    const current = await stat(temp).then((info) => info.size).catch(() => 0);
    if (current !== offset) {
      return sendJson(res, 409, {
        error: `Reprise impossible : le serveur a ${current} octet(s) (offset demandé ${offset}).`,
        offset: current,
      });
    }
  }

  const limit = (chunked ? CHUNK_MAX_MB : MAX_UPLOAD_MB) * 1024 * 1024;
  const out = createWriteStream(temp, { flags: chunked && offset > 0 ? "a" : "w" });
  let written = 0;
  try {
    for await (const chunk of req) {
      written += chunk.length;
      if (written > limit) {
        out.destroy();
        if (!chunked) await rm(temp, { force: true });
        return send(res, 413, chunked
          ? `Morceau trop gros (max ${CHUNK_MAX_MB} Mo).`
          : `Fichier trop volumineux (max ${MAX_UPLOAD_MB} Mo).`);
      }
      if (!out.write(chunk)) await once(out, "drain");
    }
    await new Promise((resolveEnd, rejectEnd) => {
      out.end((error) => (error ? rejectEnd(error) : resolveEnd()));
    });
  } catch (error) {
    out.destroy();
    await rm(temp, { force: true });
    throw error;
  }

  const total = offset + written;
  if (!done) {
    return sendJson(res, 200, { ok: true, offset: total });
  }

  await rename(temp, destination);
  console.log(`[retro] dépôt : ${system.id}/${fileName} (${(total / 1048576).toFixed(1)} Mo)`);

  // La jaquette de ce jeu est récupérée en tâche de fond (sans bloquer la réponse).
  await syncLibrary();
  startCoverJob({ systems: [system.id] });

  return sendJson(res, 200, {
    ok: true,
    system: system.id,
    file: fileName,
    size: total,
    playUrl: `/play.html?system=${encodeURIComponent(system.id)}&file=${encodeURIComponent(fileName)}`,
  });
}

/* -------------------------------------------------------------- netplay/ICE */

const ICE_SERVERS_DEFAULT = [
  { urls: "stun:stun.l.google.com:19302" },
  { urls: "stun:stun1.l.google.com:19302" },
  { urls: "turn:openrelay.metered.ca:80", username: "openrelayproject", credential: "openrelayproject" },
  { urls: "turn:openrelay.metered.ca:443", username: "openrelayproject", credential: "openrelayproject" },
  { urls: "turn:openrelay.metered.ca:443?transport=tcp", username: "openrelayproject", credential: "openrelayproject" },
];

function iceServers() {
  const raw = (process.env.NETPLAY_ICE_SERVERS || "").trim();
  if (!raw) return ICE_SERVERS_DEFAULT;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length) return parsed;
    console.warn("[retro] NETPLAY_ICE_SERVERS doit être un tableau JSON, valeur ignorée");
  } catch {
    console.warn("[retro] NETPLAY_ICE_SERVERS illisible (JSON attendu), valeur ignorée");
  }
  return ICE_SERVERS_DEFAULT;
}

function siteConfig() {
  let netplayServer = (process.env.NETPLAY_SERVER || "").trim();
  // URL absolue avec trailing slash (format attendu par EmulatorJS)
  if (netplayServer && !/^https?:\/\//i.test(netplayServer)) {
    netplayServer = `https://${netplayServer}`;
  }
  if (netplayServer && !netplayServer.endsWith("/")) netplayServer += "/";
  return {
    name: SITE_NAME,
    netplayServer,
    netplayEnabled: Boolean(netplayServer),
    netplayIceServers: iceServers(),
  };
}

/* -------------------------------------------------------------------- routeur */

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

    // Journal : indispensable pour diagnostiquer un « Network Error » côté navigateur.
    const startedAt = Date.now();
    res.on("finish", () => {
      if (res.statusCode >= 400 || url.pathname.startsWith("/play")) {
        console.log(`[retro] ${req.method} ${url.pathname} → ${res.statusCode} (${Date.now() - startedAt} ms)`);
      }
    });

    if (url.pathname === "/healthz") return send(res, 200, "ok");
    // favicon : la même image Kirby, servie depuis public/
    if (url.pathname === "/favicon.ico") {
      return await sendFile(req, res, join(PUBLIC_DIR, "favicon.png"), { maxAge: 86400 });
    }
    if (url.pathname === "/api/config") return sendJson(res, 200, siteConfig());
    if (url.pathname === "/api/library") return sendJson(res, 200, await buildLibrary());
    if (url.pathname === "/api/covers/status") return sendJson(res, 200, coverJobStatus());

    if (url.pathname === "/api/covers/refresh") {
      if (req.method !== "POST") return send(res, 405, "Utilise POST.");
      if (!UPLOAD_TOKEN) return send(res, 403, "Renseigne UPLOAD_TOKEN dans le .env.");
      if (!tokenMatches(providedToken(req))) return send(res, 401, "Jeton invalide.");
      const systems = (url.searchParams.get("system") || "").split(",").map((value) => value.trim()).filter(Boolean);
      return sendJson(res, 202, startCoverJob({ systems: systems.length ? systems : null }));
    }

    if (url.pathname === "/api/upload") return await handleUpload(req, res, url);

    if (req.method !== "GET" && req.method !== "HEAD") return send(res, 405, "Méthode non autorisée.");

    if (url.pathname.startsWith("/ejs/")) {
      return await sendFile(req, res, safeJoin(EJS_DIR, url.pathname.slice(4)), { immutable: true });
    }
    if (url.pathname.startsWith("/covers/")) {
      return await sendFile(req, res, safeJoin(COVERS_DIR, url.pathname.slice(7)), { maxAge: 86400 });
    }
    if (url.pathname.startsWith("/roms/")) {
      return await sendFile(req, res, safeJoin(ROMS_DIR, url.pathname.slice(5)));
    }

    const relative = url.pathname === "/" ? "/index.html" : url.pathname;
    return await sendFile(req, res, safeJoin(PUBLIC_DIR, relative));
  } catch (error) {
    console.error("[retro] erreur :", error);
    send(res, 500, "Erreur serveur.");
  }
});

server.listen(PORT, HOST, () => {
  console.log(`[retro] ${SITE_NAME} écoute sur http://${HOST}:${PORT}`);
  console.log(`[retro] roms=${ROMS_DIR} ejs=${EJS_DIR} covers=${COVERS_DIR} db=${CATALOG_DB}`);
  console.log(`[retro] ${CATALOG.countGames()} jeu(x) en base, upload=${UPLOAD_TOKEN ? "actif" : "désactivé"}`);
  const np = siteConfig().netplayServer || "(désactivé)";
  console.log(`[retro] netplay=${np}`);
});
