import sql from '../sql';
import tables from '../tables';

const table = tables.find((t) => t.name === 'geometry_index');

/**
 * GEO-006: spatial index for overlap candidates, plus the readiness gate that
 * stops GEO-007 validating against an empty post-upgrade index (D-4).
 *
 * No backfill — existing installs repopulate through sync → reset.
 */
const up = async (db) => {
  await sql.createTable(db, table.name, table.fields);
  // Single-column bbox indexes: SQLite picks the most selective for range
  // conditions; a composite across all four would not be used (GEO-006 D-1).
  await db.execAsync(`
    CREATE INDEX IF NOT EXISTS idx_geometry_index_minLat ON geometry_index (minLat);
    CREATE INDEX IF NOT EXISTS idx_geometry_index_maxLat ON geometry_index (maxLat);
    CREATE INDEX IF NOT EXISTS idx_geometry_index_minLon ON geometry_index (minLon);
    CREATE INDEX IF NOT EXISTS idx_geometry_index_maxLon ON geometry_index (maxLon);
  `);
  await sql.addNewColumn(db, 'config', 'geometryIndexReady', 'TINYINT DEFAULT 0');
};

const down = (db) => sql.dropTable(db, table.name);

export { up, down };
