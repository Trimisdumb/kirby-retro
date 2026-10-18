/**
 * Catalogue SQLite du site rétro (node:sqlite, aucune dépendance externe).
 *
 * Deux tables :
 *   systems — les consoles supportées (id, libellé, core, extensions)
 *   games   — un enregistrement par ROM présente sur le disque, plus sa jaquette
 *
 * Le disque reste la source de vérité pour l'existence des fichiers : `syncGames`
 * ajoute/met à jour les lignes et supprime celles dont le fichier a disparu,
 * sans jamais toucher aux jaquettes déjà téléchargées.
 */
import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";

export function openCatalog(file) {
  mkdirSync(dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS games (
      system       TEXT    NOT NULL,
      file         TEXT    NOT NULL,
      title        TEXT    NOT NULL,
      region       TEXT,
      year         TEXT,
      size         INTEGER,
      mtime        INTEGER,
      cover        TEXT,
      cover_source TEXT,
      match_name   TEXT,
      updated_at   INTEGER,
      PRIMARY KEY (system, file)
    );
    CREATE INDEX IF NOT EXISTS games_system_idx ON games (system);
    CREATE TABLE IF NOT EXISTS systems (
      id         TEXT PRIMARY KEY,
      label      TEXT NOT NULL,
      core       TEXT NOT NULL,
      extensions TEXT NOT NULL,
      position   INTEGER
    );
  `);

  const upsertSystem = db.prepare(`
    INSERT INTO systems (id, label, core, extensions, position)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      label = excluded.label, core = excluded.core,
      extensions = excluded.extensions, position = excluded.position
  `);
  const upsertGame = db.prepare(`
    INSERT INTO games (system, file, title, region, year, size, mtime, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(system, file) DO UPDATE SET
      title = excluded.title, region = excluded.region, year = excluded.year,
      size = excluded.size, mtime = excluded.mtime, updated_at = excluded.updated_at
  `);
  const setCover = db.prepare(`
    UPDATE games SET cover = ?, cover_source = ?, match_name = ?, updated_at = ?
    WHERE system = ? AND file = ?
  `);
  const deleteGame = db.prepare(`DELETE FROM games WHERE system = ? AND file = ?`);
  const allGames = db.prepare(`SELECT * FROM games ORDER BY system, title COLLATE NOCASE`);
  const systemsWithCount = db.prepare(`
    SELECT s.*, (SELECT COUNT(*) FROM games g WHERE g.system = s.id) AS count
    FROM systems s ORDER BY s.position
  `);
  const missingCovers = db.prepare(`
    SELECT * FROM games WHERE cover IS NULL OR cover = '' ORDER BY system, title COLLATE NOCASE
  `);
  const gamesOfSystem = db.prepare(`SELECT * FROM games WHERE system = ? ORDER BY title COLLATE NOCASE`);

  return {
    raw: db,

    saveSystems(systems) {
      db.exec("BEGIN");
      try {
        systems.forEach((system, index) => {
          upsertSystem.run(system.id, system.label, system.core, system.ext.join(","), index);
        });
        db.exec("COMMIT");
      } catch (error) {
        db.exec("ROLLBACK");
        throw error;
      }
    },

    /** rows : { system, file, title, region, year, size, mtime } */
    syncGames(rows) {
      const existing = new Set(allGames.all().map((row) => `${row.system}\u0000${row.file}`));
      const now = Date.now();
      const seen = new Set();
      db.exec("BEGIN");
      try {
        for (const row of rows) {
          const key = `${row.system}\u0000${row.file}`;
          seen.add(key);
          // SQLite est typé dynamiquement : on force les chaînes là où on attend du texte
          // (sinon une année numérique ressort en « 2005.0 »).
          upsertGame.run(
            String(row.system),
            String(row.file),
            String(row.title),
            row.region == null || row.region === "" ? null : String(row.region),
            row.year == null || row.year === "" ? null : String(row.year),
            Number.isFinite(Number(row.size)) ? Number(row.size) : null,
            Number.isFinite(Number(row.mtime)) ? Number(row.mtime) : null,
            now,
          );
        }
        for (const key of existing) {
          if (seen.has(key)) continue;
          const [system, file] = key.split("\u0000");
          deleteGame.run(system, file);
        }
        db.exec("COMMIT");
      } catch (error) {
        db.exec("ROLLBACK");
        throw error;
      }
    },

    setCover(system, file, { cover, source, matchName }) {
      setCover.run(cover, source ?? null, matchName ?? null, Date.now(), system, file);
    },

    allGames: () => allGames.all(),
    gamesOfSystem: (system) => gamesOfSystem.all(system),
    systemsWithCount: () => systemsWithCount.all(),
    gamesMissingCover: () => missingCovers.all(),
    countGames: () => Number(db.prepare("SELECT COUNT(*) AS n FROM games").get()?.n ?? 0),

    close() {
      db.close();
    },
  };
}
