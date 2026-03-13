import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const dbPath = path.resolve(process.cwd(), 'worldbuilder.db');
export const db = new Database(dbPath);

export function initDb() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS universes (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS entities (
      id TEXT PRIMARY KEY,
      universe_id TEXT,
      type TEXT NOT NULL,
      name TEXT NOT NULL,
      description TEXT,
      tags TEXT,
      image TEXT,
      data TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY,
      universe_id TEXT,
      title TEXT NOT NULL,
      description TEXT,
      event_date TEXT,
      order_index INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS map_nodes (
      id TEXT PRIMARY KEY,
      universe_id TEXT,
      parent_id TEXT,
      type TEXT NOT NULL, -- 'galaxy', 'system', 'planet', 'hex'
      name TEXT NOT NULL,
      description TEXT,
      x REAL,
      y REAL,
      data TEXT, -- JSON for extra properties like biome, poi
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT
    );

    CREATE TABLE IF NOT EXISTS random_tables (
      id TEXT PRIMARY KEY,
      universe_id TEXT,
      name TEXT NOT NULL,
      description TEXT,
      type TEXT,
      rollType TEXT,
      entries TEXT,
      conditions TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  try { db.exec("ALTER TABLE entities ADD COLUMN universe_id TEXT;"); } catch (e) {}
  try { db.exec("ALTER TABLE events ADD COLUMN universe_id TEXT;"); } catch (e) {}
  try { db.exec("ALTER TABLE map_nodes ADD COLUMN universe_id TEXT;"); } catch (e) {}
  try { db.exec("ALTER TABLE entities ADD COLUMN image TEXT;"); } catch (e) {}
  try { db.exec("ALTER TABLE entities ADD COLUMN data TEXT;"); } catch (e) {}
  try { db.exec("ALTER TABLE random_tables ADD COLUMN rollType TEXT;"); } catch (e) {}

  // Migrate existing data to a default universe if they don't have one
  const defaultUniverseId = 'default-universe';
  db.exec(`
    INSERT OR IGNORE INTO universes (id, name, description) VALUES ('${defaultUniverseId}', 'Default Universe', 'Migrated default universe.');
    UPDATE entities SET universe_id = '${defaultUniverseId}' WHERE universe_id IS NULL;
    UPDATE events SET universe_id = '${defaultUniverseId}' WHERE universe_id IS NULL;
    UPDATE map_nodes SET universe_id = '${defaultUniverseId}' WHERE universe_id IS NULL;
  `);
}
