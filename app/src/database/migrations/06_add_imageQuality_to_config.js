import sql from '../sql';

const tableName = 'config';
const fieldName = 'imageQuality';
const fieldType = "VARCHAR(20) DEFAULT 'low'";

const up = async (db) => {
  await sql.addNewColumn(db, tableName, fieldName, fieldType);
};

const down = () => {
  throw new Error(
    'Migration 06 is irreversible. To remove imageQuality, create a new forward migration.',
  );
};

export { up, down };
