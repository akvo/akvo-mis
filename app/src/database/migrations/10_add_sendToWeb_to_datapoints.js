import sql from '../sql';

const tableName = 'datapoints';
const fieldName = 'sendToWeb';
const fieldType = 'TINYINT DEFAULT 0';

const up = async (db) => {
  await sql.addNewColumn(db, tableName, fieldName, fieldType);
  // No back-fill. Drafts that already reached the web carry a draftId, which keeps
  // them syncing on its own (see selectSubmissionToSync); everything else is a
  // local-born draft that now stays on the device until the user opts in.
};

// dropColumn uses a DROP TABLE + RENAME pattern with no wrapping transaction, so a
// crash between those steps would destroy every datapoint. Adding a nullable column
// with a safe default has no meaningful rollback — ship a new forward migration
// instead if the column must go.
const down = () => {
  throw new Error(
    'Migration 10 is irreversible. To remove sendToWeb, create a new forward migration.',
  );
};

export { up, down };
