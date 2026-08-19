import sql from '../sql';

const tableName = 'config';
const fieldName = 'saveToGallery';

const up = async (db) => {
  await sql.addNewColumn(db, tableName, fieldName, 'TINYINT DEFAULT 0');
};

const down = () => {
  throw new Error(
    'Migration 09 is irreversible. To remove saveToGallery, create a new forward migration.',
  );
};

export { up, down };
