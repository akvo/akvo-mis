import sql from '../sql';

/**
 * GEO-006/GEO-007: the server's absolute geoshape-answer count, per form.
 *
 * `/datapoint-list` returns `geometry_total` from the cursor-free set, which is the only number
 * that can tell a gapped index from a complete one — the device compares it against its own
 * `geometry_index` row count at validation time. The sync queue cannot hold it, because the
 * queue is cleared the moment a sync finishes, which is exactly when the comparison matters.
 *
 * A JSON map keyed by backend form id, on the single config row.
 * ponytail: a map in a TEXT column, not a table. It holds one small integer per form the
 * enumerator is assigned; give it a table if that ever stops being a handful.
 */
const up = async (db) => {
  await sql.addNewColumn(db, 'config', 'geometryTotals', 'TEXT');
};

const down = async (db) => {
  await sql.dropColumn(db, 'config', 'geometryTotals');
};

export { up, down };
