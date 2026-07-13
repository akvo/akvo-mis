import sql from '../sql';

const tableName = 'datapoints';

const up = async (db) => {
  // Per-submission idempotency token. Minted on-device at submit time and resent
  // unchanged on every retry, so the backend can recognise a replay.
  //
  // locallyCreated is deliberately NOT touched here. It is an immutable origin
  // flag (1 = made on this device, 0 = downloaded). Migration 05 back-filled it
  // onto downloaded rows too, which no UPDATE can undo -- device-synced and
  // downloaded rows are already indistinguishable among the back-filled rows.
  // Correct provenance comes from a fresh database (dev devices are wiped), not
  // from SQL. See APP-255 D-17.
  await sql.addNewColumn(db, tableName, 'submissionKey', 'TEXT');
};

const down = () => {
  throw new Error('Migration 08 is irreversible. Create a new forward migration instead.');
};

export { up, down };
