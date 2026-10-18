#!/usr/bin/env node
/**
 * Récupération des jaquettes en ligne de commande (cron, maintenance, premier lancement).
 *
 *   docker compose exec retro node scripts/fetch-covers.mjs
 *   docker compose exec retro node scripts/fetch-covers.mjs --system n64,nds
 *   docker compose exec retro node scripts/fetch-covers.mjs --all      (retélécharge tout)
 */
import { readdir, readFile, stat } from "node:fs/promises";
import { extname, join } from "node:path";

import { openCatalog } from "../src/catalog.mjs";
import { fetchMissingCovers, LIBRETRO_SYSTEMS, parseRomName } from "../src/covers.mjs";

const SYSTEMS = [
  { id: "nes", ext: ["nes", "fds", "unf", "unif", "zip"] },
  { id: "snes", ext: ["smc", "sfc", "swc", "fig", "zip"] },
  { id: "gb", ext: ["gb", "gbc", "dmg", "zip"] },
  { id: "gba", ext: ["gba", "agb", "zip"] },
  { id: "n64", ext: ["n64", "z64", "v64", "u1", "ndd", "zip"] },
  { id: "nds", ext: ["nds", "zip"] },
  { id: "psx", ext: ["cue", "chd", "pbp", "iso", "img", "mdf", "bin"] },
  { id: "segaMD", ext: ["md", "gen", "smd", "bin", "zip"] },
  { id: "segaMS", ext: ["sms", "zip"] },
  { id: "segaGG", ext: ["gg", "zip"] },
  { id: "pce", ext: ["pce", "sgx", "zip"] },
  { id: "atari2600", ext: ["a26", "bin"] },
  { id: "lynx", ext: ["lnx", "zip"] },
  { id: "c64", ext: ["d64", "t64", "prg", "tap", "crt", "nib", "zip"] },
  { id: "vb", ext: ["vb", "vboy", "zip"] },
];

const args = process.argv.slice(2);
const ROMS_DIR = process.env.ROMS_DIR || "/data/roms";
const COVERS_DIR = process.env.COVERS_DIR || "/data/covers";
const STATE_DIR = process.env.STATE_DIR || "/data/state";
const CATALOG_DB = process.env.CATALOG_DB || join(STATE_DIR, "catalog.db");
const everything = args.includes("--all");
const systemArg = args.find((arg) => arg.startsWith("--system="))?.slice(9)
  || (args.includes("--system") ? args[args.indexOf("--system") + 1] : "");
const selected = systemArg ? systemArg.split(",").map((value) => value.trim()).filter(Boolean) : null;

const catalog = openCatalog(CATALOG_DB);

// Titres/années/jaquettes forcés à la main (mêmes règles que le serveur).
const overrides = await readFile(join(ROMS_DIR, "library.json"), "utf8")
  .then((raw) => JSON.parse(raw))
  .catch(() => ({}));

// Rescanne le disque : la base doit refléter l'état réel avant de chercher des jaquettes.
const rows = [];
for (const system of SYSTEMS) {
  const dir = join(ROMS_DIR, system.id);
  const entries = await readdir(dir, { withFileTypes: true }).catch(() => []);
  const names = new Set(entries.filter((entry) => entry.isFile()).map((entry) => entry.name));
  for (const entry of entries) {
    if (!entry.isFile() || entry.name.startsWith(".")) continue;
    const ext = extname(entry.name).slice(1).toLowerCase();
    if (!system.ext.includes(ext)) continue;
    if (ext === "bin" && names.has(entry.name.replace(/\.bin$/iu, ".cue"))) continue;
    const info = await stat(join(dir, entry.name)).catch(() => null);
    if (!info) continue;
    const parsed = parseRomName(entry.name);
    const override = overrides[`${system.id}/${entry.name}`] || {};
    rows.push({
      system: system.id, file: entry.name,
      title: override.title || parsed.title,
      region: override.region || parsed.region,
      year: override.year || parsed.year,
      size: info.size, mtime: Math.floor(info.mtimeMs),
    });
  }
}
catalog.syncGames(rows);

let games = everything ? catalog.allGames() : catalog.gamesMissingCover();
if (selected) games = games.filter((game) => selected.includes(game.system));

console.log(`${games.length} jeu(x) à traiter${selected ? ` (${selected.join(", ")})` : ""}…`);
for (const game of games) {
  if (!LIBRETRO_SYSTEMS[game.system]) console.log(`   (${game.system} : pas de source de jaquettes)`);
}

const summary = await fetchMissingCovers({
  games,
  coversDir: COVERS_DIR,
  cacheDir: join(STATE_DIR, "libretro-index"),
  onCover: (system, file, info) => catalog.setCover(system, file, info),
});

console.log("");
console.log(`Terminé : ${summary.found} jaquette(s) récupérée(s), ${summary.missing} sans résultat.`);
catalog.close();
