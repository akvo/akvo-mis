import sql from '../sql';

const tableName = 'config';
const fieldName = 'updateSkippedUntil';
const fieldType = 'DATETIME';

const up = async (db) => {
  await sql.addNewColumn(db, tableName, fieldName, fieldType);
};

const down = () => {
  throw new Error(
    'Migration 07 is irreversible. To remove updateSkippedUntil, create a new forward migration.',
  );
};

export { up, down };
