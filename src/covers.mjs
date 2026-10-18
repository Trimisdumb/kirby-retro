/**
 * Récupération automatique des jaquettes depuis la base libre libretro-thumbnails
 * (https://thumbnails.libretro.com) — aucune clé API, aucune inscription.
 *
 * Principe : pour chaque console, on récupère l'index du dossier `Named_Boxarts`
 * (mis en cache sur disque), on cherche la ROM par correspondance de nom, puis on
 * télécharge l'image en local. Si aucune jaquette n'existe, on retente avec
 * `Named_Snaps` (captures d'écran).
 */
import { mkdir, readFile, writeFile, stat } from "node:fs/promises";
import { join } from "node:path";

const LIBRETRO = "https://thumbnails.libretro.com";
const INDEX_MAX_AGE_MS = 7 * 24 * 3600 * 1000;

/** Console interne → dossier libretro-thumbnails. */
export const LIBRETRO_SYSTEMS = {
  nes: "Nintendo - Nintendo Entertainment System",
  snes: "Nintendo - Super Nintendo Entertainment System",
  gb: "Nintendo - Game Boy",
  gba: "Nintendo - Game Boy Advance",
  n64: "Nintendo - Nintendo 64",
  nds: "Nintendo - Nintendo DS",
  psx: "Sony - PlayStation",
  segaMD: "Sega - Mega Drive - Genesis",
  segaMS: "Sega - Master System - Mark III",
  segaGG: "Sega - Game Gear",
  pce: "NEC - PC Engine - TurboGrafx 16",
  atari2600: "Atari - 2600",
  lynx: "Atari - Lynx",
  c64: "Commodore - 64",
  vb: "Nintendo - Virtual Boy",
  // Ajouts v1.3.0
  sega32x: "Sega - 32X",
  segaSaturn: "Sega - Saturn",
  dreamcast: "Sega - Dreamcast",
  arcade: "FBNeo - Arcade Games",
  psp: "Sony - PlayStation Portable",
  gamecube: "Nintendo - GameCube",
  wii: "Nintendo - Wii",
  ps2: "Sony - PlayStation 2",
  "3ds": "Nintendo - Nintendo 3DS",
  cpc: "Amstrad - CPC",
  apple2: "Apple - Apple II",
  pc88: "NEC - PC-88",
  pokemini: "Nintendo - Pokemon Mini",
};

/** Les deux dossiers d'images essayés, dans l'ordre. */
const FOLDERS = ["Named_Boxarts", "Named_Snaps"];

function stripBrackets(name) {
  return name.replace(/\[[^\]]*\]/gu, " ").replace(/\s+/gu, " ").trim();
}

function baseName(name) {
  return name.replace(/\.[^.]+$/u, "");
}

/** Clé de comparaison tolérante : minuscules, accents/ponctuation/espaces ignorés. */
export function normalizeKey(name) {
  return baseName(name)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/gu, "")
    .toLowerCase()
    .replace(/\.[a-z0-9]{2,4}$/u, "")
    .replace(/[^a-z0-9]+/gu, "");
}

/** Variante « ponctuation harmonisée » : les _ des noms de ROM deviennent des virgules. */
function harmonize(name) {
  return baseName(stripBrackets(name))
    .replace(/_/gu, ",")
    .replace(/\s*,\s*/gu, ",")
    .replace(/\s+/gu, " ")
    .trim()
    .toLowerCase();
}

/** Titre seul, sans les étiquettes entre parenthèses (dernier recours de correspondance). */
function titleOnly(name) {
  return harmonize(name).replace(/\([^)]*\)/gu, " ").replace(/\s+/gu, " ").trim();
}

/** Étiquette de région lisible, extraite des parenthèses. */
export function parseRomName(fileName) {
  const base = baseName(fileName);
  const parens = [...base.matchAll(/\(([^)]*)\)/gu)].map((match) => match[1].trim());
  const joined = parens.join(" | ");
  const regionPatterns = [
    [/france/i, "FRA"], [/germany/i, "GER"], [/spain/i, "SPA"], [/italy/i, "ITA"],
    [/netherlands/i, "NLD"], [/sweden/i, "SWE"], [/europe/i, "EUR"], [/usa/i, "USA"],
    [/japan/i, "JAP"], [/korea/i, "KOR"], [/china/i, "CHN"], [/australia/i, "AUS"],
    [/canada/i, "CAN"], [/brazil/i, "BRA"], [/world/i, "WLD"],
  ];
  const region = regionPatterns.find(([pattern]) => pattern.test(joined))?.[1] ?? null;
  const year = joined.match(/\b(19|20)\d{2}\b/u)?.[0] ?? null;
  const title = base
    .replace(/\([^)]*\)/gu, " ")
    .replace(/\[[^\]]*\]/gu, " ")
    .replace(/[_.]+/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
  return {
    title: title ? title.charAt(0).toUpperCase() + title.slice(1) : base,
    region,
    year,
  };
}

async function readCachedIndex(cacheFile) {
  const info = await stat(cacheFile).catch(() => null);
  if (!info || Date.now() - info.mtimeMs > INDEX_MAX_AGE_MS) return null;
  try {
    const parsed = JSON.parse(await readFile(cacheFile, "utf8"));
    return Array.isArray(parsed?.names) ? parsed.names : null;
  } catch {
    return null;
  }
}

async function downloadIndex(system, folder, cacheDir, log) {
  const cacheFile = join(cacheDir, `${system}-${folder}.json`);
  const cached = await readCachedIndex(cacheFile);
  if (cached) return cached;

  const url = `${LIBRETRO}/${encodeURIComponent(LIBRETRO_SYSTEMS[system])}/${folder}/`;
  log?.(`   index ${system}/${folder}…`);
  const response = await fetch(url, { signal: AbortSignal.timeout(120_000) });
  if (!response.ok) {
    log?.(`   ! ${folder} indisponible pour ${system} (HTTP ${response.status})`);
    await mkdir(cacheDir, { recursive: true });
    await writeFile(cacheFile, JSON.stringify({ names: [], fetchedAt: Date.now(), error: response.status }));
    return [];
  }
  const html = await response.text();
  const names = [];
  const pattern = /href="([^"]+\.(?:png|jpe?g))"/giu;
  let match;
  while ((match = pattern.exec(html))) {
    try {
      names.push(decodeURIComponent(match[1]));
    } catch {
      names.push(match[1]);
    }
  }
  await mkdir(cacheDir, { recursive: true });
  await writeFile(cacheFile, JSON.stringify({ names, fetchedAt: Date.now() }));
  log?.(`   ${names.length} images dans ${system}/${folder}`);
  return names;
}

/** Cherche la meilleure correspondance pour un nom de ROM dans une liste d'images. */
export function findMatch(romFile, names) {
  const wantedFull = baseName(romFile).toLowerCase();
  const wantedHarmonized = harmonize(romFile);
  const wantedTitle = titleOnly(romFile);

  const exact = names.find((name) => baseName(name).toLowerCase() === wantedFull);
  if (exact) return { name: exact, how: "exact" };

  const harmonized = names.find((name) => harmonize(name) === wantedHarmonized);
  if (harmonized) return { name: harmonized, how: "harmonisée" };

  const wantedKey = normalizeKey(romFile);
  const normalized = names.find((name) => normalizeKey(name) === wantedKey);
  if (normalized) return { name: normalized, how: "normalisée" };

  if (wantedTitle.length >= 4) {
    // Priorité à une version de la même région si elle existe, sinon premier résultat.
    const regionTag = (baseName(romFile).match(/\((usa|europe|japan|world|france|germany|spain|italy)\)/iu) || [])[0];
    const candidates = names.filter((name) => titleOnly(name) === wantedTitle);
    if (candidates.length) {
      const sameRegion = regionTag
        ? candidates.find((name) => name.toLowerCase().includes(regionTag.toLowerCase()))
        : null;
      return { name: sameRegion || candidates[0], how: "titre seul" };
    }
  }

  return null;
}

/**
 * Télécharge les jaquettes manquantes.
 * @param {object} options
 * @param {Array}  options.games      lignes du catalogue (system, file, cover)
 * @param {string} options.coversDir  dossier de destination
 * @param {string} options.cacheDir   dossier de cache des index
 * @param {Function} options.onCover  callback (system, file, {cover, source, matchName})
 * @param {Function} options.log
 */
export async function fetchMissingCovers({ games, coversDir, cacheDir, onCover, log = console.log }) {
  const bySystem = new Map();
  for (const game of games) {
    if (game.cover) continue;
    if (!LIBRETRO_SYSTEMS[game.system]) {
      log(`   (${game.system} n'a pas de source de jaquettes)`);
      continue;
    }
    if (!bySystem.has(game.system)) bySystem.set(game.system, []);
    bySystem.get(game.system).push(game);
  }

  const summary = { found: 0, missing: 0, systems: 0 };
  for (const [system, list] of bySystem) {
    summary.systems += 1;
    let names = [];
    let folderUsed = FOLDERS[0];
    for (const folder of FOLDERS) {
      names = await downloadIndex(system, folder, cacheDir, log).catch((error) => {
        log(`   ! index ${system}/${folder} : ${error.message}`);
        return [];
      });
      if (names.length) {
        folderUsed = folder;
        break;
      }
    }
    if (!names.length) {
      summary.missing += list.length;
      continue;
    }

    for (const game of list) {
      const match = findMatch(game.file, names);
      if (!match) {
        summary.missing += 1;
        log(`   ? ${game.file} — aucune image trouvée`);
        continue;
      }
      const slug = baseName(game.file).replace(/[^\w.-]+/gu, "_").slice(0, 120);
      const targetDir = join(coversDir, system);
      await mkdir(targetDir, { recursive: true });
      const target = join(targetDir, `${slug}.png`);
      try {
        const response = await fetch(`${LIBRETRO}/${encodeURIComponent(LIBRETRO_SYSTEMS[system])}/${folderUsed}/${encodeURIComponent(match.name)}`, {
          signal: AbortSignal.timeout(60_000),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const buffer = Buffer.from(await response.arrayBuffer());
        await writeFile(target, buffer);
        const cover = `/covers/${system}/${slug}.png`;
        onCover?.(system, game.file, {
          cover,
          source: `libretro/${folderUsed}`,
          matchName: match.name,
        });
        summary.found += 1;
        log(`   ✓ ${system}/${game.file} ← ${match.name} (${match.how}, ${(buffer.length / 1024).toFixed(0)} Ko)`);
      } catch (error) {
        summary.missing += 1;
        log(`   ! ${game.file} : ${error.message}`);
      }
    }
  }
  return summary;
}
