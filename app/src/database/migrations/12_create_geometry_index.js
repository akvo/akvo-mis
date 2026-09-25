import sql from '../sql';
import tables from '../tables';

const table = tables.find((t) => t.name === 'geometry_index');

/**
 * GEO-006: spatial index for overlap candidates, plus the two config columns that
 * decide whether GEO-007 may trust it.
 *
 * No backfill — existing installs repopulate through sync → reset.
 *
 * `geometryIndexReady` is the gate (D-4): 0 means no full geometry pull has landed
 * since this migration or the last reset, and validation refuses rather than
 * reporting "no overlap" over an empty index.
 *
 * `geometryTotals` is a JSON map of backend form id → the server's `geometry_total`,
 * the cursor-free count of geoshape answers. It is the only number that tells a gapped
 * index from a complete one, and it cannot live on `datapoint_sync_queue` because that
 * is cleared the moment a sync finishes — which is exactly when validation needs it (D-9).
 * ponytail: a map in a TEXT column, not a table. It holds one small integer per assigned
 * form; give it a table if that ever stops being a handful.
 *
 * `geometryReadyForms` is a JSON array of backend form ids whose index a full, error-free
 * geometry pull has populated. `geometryIndexReady` is one flag for the device, but the index is
 * filled form by form: a registration form assigned after that flag flipped was pulled through
 * the cursor-filtered listing, got none of its older datapoints, and its index could never be
 * built. See `formsOwingFullPull`. Same ponytail as `geometryTotals`: one id per assigned form.
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
  await sql.addNewColumn(db, 'config', 'geometryTotals', 'TEXT');
  await sql.addNewColumn(db, 'config', 'geometryReadyForms', 'TEXT');
};

const down = (db) => sql.dropTable(db, table.name);

export { up, down };
