import sql from '../sql';

const tableName = 'config';
const fieldNames = ['validatePolygonShape', 'validatePolygonArea'];

/**
 * Both switches default to 1, so ALTER TABLE backfills existing rows to "block".
 * A device that upgrades mid-programme therefore lands on the strict setting rather than
 * silently downgrading everything it has already been enforcing (GEO-002 D-4).
 */
const up = async (db) => {
  await fieldNames.reduce(async (prev, fieldName) => {
    await prev;
    await sql.addNewColumn(db, tableName, fieldName, 'TINYINT DEFAULT 1');
  }, Promise.resolve());
};

const down = () => {
  throw new Error(
    'Migration 11 is irreversible. To remove the polygon validation switches, create a new forward migration.',
  );
};

export { up, down };
