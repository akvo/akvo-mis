import sql from '../sql';

const tableName = 'config';
const fieldName = 'darkModePreference';

const up = async (db) => {
  await sql.addNewColumn(db, tableName, fieldName, "VARCHAR(10) DEFAULT 'auto'");
};

const down = () => {
  throw new Error(
    'Migration 13 is irreversible. To remove darkModePreference, create a new forward migration.',
  );
};

export { up, down };
