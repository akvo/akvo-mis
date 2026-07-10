import sql from '../sql';

const tableName = 'datapoints';

const up = async (db) => {
  // Per-submission idempotency token. Minted on-device at submit time and resent
  // unchanged on every retry, so the backend can recognise a replay.
  await sql.addNewColumn(db, tableName, 'submissionKey', 'TEXT');

  // Migration 05 back-filled locallyCreated = 1 onto every existing row, including
  // rows that had been downloaded from the server. Any row carrying a syncedAt
  // timestamp is, by definition, already known to the backend.
  await db.execAsync(`UPDATE ${tableName} SET locallyCreated = 0 WHERE syncedAt IS NOT NULL`);
};

// The pre-migration locallyCreated values were wrong, so there is nothing to
// restore. To change the flag semantics, create a new forward migration.
const down = () => {
  throw new Error('Migration 08 is irreversible. Create a new forward migration instead.');
};

export { up, down };
