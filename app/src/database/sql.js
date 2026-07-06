/**
 * Creates a table if it does not already exist.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to create.
 * @param {Object} fields - An object representing the column names and their corresponding data types.
 * @returns {Promise<void>} A promise that resolves when the table has been created.
 */
const createTable = async (db, table, fields) => {
  const columns = Object.entries(fields)
    .map(([name, type]) => `${name} ${type}`)
    .join(', ');
  await db.execAsync(`
    CREATE TABLE IF NOT EXISTS ${table} (
      ${columns}
    );
  `);
  const res = await db.getFirstAsync(`PRAGMA table_info(${table})`);
  return res;
};

/**
 * Updates a row in the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to update the row in.
 * @param {Object} [conditions={ id: 1 }] - An object representing the conditions for identifying the row to update.
 * @param {Object} values - An object representing the column names and their corresponding values to be updated.
 * @returns {Promise<void>} A promise that resolves when the row has been updated.
 */
const updateRow = async (db, table, conditions = { id: 1 }, values = {}) => {
  try {
    const setClause = Object.keys(values)
      .map((key) => `${key} = ?`)
      .join(', ');
    const whereClause = Object.keys(conditions)
      .map((key) => `${key} = ?`)
      .join(' AND ');
    const params = [...Object.values(values), ...Object.values(conditions)];
    await db.runAsync(`UPDATE ${table} SET ${setClause} WHERE ${whereClause}`, ...params);
  } catch (error) {
    throw new Error(`Error updating row in table ${table}: ${error.message}`);
  }
};

/**
 * Deletes a row from the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to delete the row from.
 * @param {number} id - The ID of the row to delete.
 * @returns {Promise<void>} A promise that resolves when the row has been deleted.
 */
const deleteRow = async (db, table, id) => {
  try {
    await db.runAsync(`DELETE FROM ${table} WHERE id = ?`, id);
  } catch (error) {
    throw new Error(`Error deleting row from table ${table}: ${error.message}`);
  }
};

/**
 * Retrieves the first row from the specified table in the database with optional conditions.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to retrieve the first row from.
 * @param {Object} [conditions={}] - An object representing the conditions for filtering rows (optional).
 * @returns {Promise<Object>} A promise that resolves to the first row in the table.
 */
const getFirstRow = async (db, table, conditions = {}) => {
  try {
    const whereClause = Object.keys(conditions).length
      ? Object.keys(conditions)
          .map((key) => (conditions[key] === null ? `${key} IS NULL` : `${key} = ?`))
          .join(' AND ')
      : false;
    // Filter out null values from params since they're handled with IS NULL
    const params = Object.values(conditions).filter((val) => val !== null);
    const query = `
      SELECT * FROM ${table}
      ${whereClause ? `WHERE ${whereClause}` : ''}
      LIMIT 1;
    `;
    const firstRow = await db.getFirstAsync(query, ...params);
    return firstRow;
  } catch (error) {
    throw new Error(`Error in getFirstRow for table ${table}: ${error.message}`);
  }
};

/**
 * Inserts a row into the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to insert the row into.
 * @param {Object} values - An object representing the column names and their corresponding values to be inserted.
 * @returns {Promise<void>} A promise that resolves when the row has been inserted.
 */
const insertRow = async (db, table, values) => {
  try {
    const columns = Object.keys(values).join(', ');
    const placeholders = Object.keys(values)
      .map(() => '?')
      .join(', ');
    const params = Object.values(values);
    const res = await db.runAsync(
      `INSERT INTO ${table} (${columns}) VALUES (${placeholders})`,
      ...params,
    );
    return res?.lastInsertRowId;
  } catch (error) {
    throw new Error(`Error inserting row into table ${table}: ${error.message}`);
  }
};

/**
 * Retrieves all rows from the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to retrieve all rows from.
 * @returns {Promise<Array>} A promise that resolves to an array of all rows in the table.
 */
const getEachRow = async (db, table) => {
  const rows = await db.getAllAsync(`SELECT * FROM ${table}`);
  return rows;
};

/**
 * Retrieves filtered rows from a specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to query.
 * @param {Object} conditions - An object representing the conditions for filtering rows.
 * @param {string} [orderBy=null] - The column name to order the results by (optional).
 * @param {string} [order='ASC'] - The order direction, either 'ASC' for ascending or 'DESC' for descending (optional).
 * @param {boolean} [collateNoCase=false] - Whether to use COLLATE NOCASE for case-insensitive matching (optional).
 * @returns {Promise<Array>} A promise that resolves to an array of filtered rows.
 */
const getFilteredRows = async (
  db,
  table,
  conditions,
  orderBy = null,
  order = 'ASC',
  collateNoCase = false,
) => {
  try {
    if (!conditions || Object.keys(conditions).length === 0) {
      throw new Error('Conditions cannot be empty');
    }

    const whereClause = Object.keys(conditions)
      .map((key) => (conditions[key] === null ? `${key} IS NULL` : `${key} = ?`))
      .join(' AND ');

    // Filter out null values from params since they're handled with IS NULL
    const params = Object.values(conditions).filter((val) => val !== null);

    // Properly format the ORDER BY clause with COLLATE NOCASE if needed
    let orderClause = '';
    if (orderBy) {
      const collateClause = collateNoCase ? ' COLLATE NOCASE' : '';
      orderClause = `ORDER BY ${orderBy}${collateClause} ${order}`;
    }

    const query = `SELECT * FROM ${table} WHERE ${whereClause} ${orderClause}`.trim();

    const rows = await db.getAllAsync(query, ...params);
    return rows;
  } catch (error) {
    throw new Error(`Error in getFilteredRows for table ${table}: ${error.message}`);
  }
};

/**
 * Executes a custom query on the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} query - The SQL query to execute.
 * @param {Array} [params=[]] - The parameters to pass to the query (optional).
 * @returns {Promise<Array>} A promise that resolves to the result of the query.
 */
const executeQuery = async (db, query, params = []) => {
  try {
    const result = await db.getAllAsync(query, ...params);
    return result;
  } catch (error) {
    throw new Error(`Error executing query: ${error.message}`);
  }
};

/**
 * Drop a table from the database.
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to drop.
 * @returns {Promise<void>} A promise that resolves when the table has been dropped.
 */
const dropTable = async (db, table) => {
  await db.execAsync(`DROP TABLE IF EXISTS ${table}`);
};

/**
 * Truncate a table from the database and check cascade.
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to truncate.
 * @returns {Promise<void>} A promise that resolves when the table has been truncated.
 */
const truncateTable = async (db, table) => {
  // Disable foreign key constraints
  await db.execAsync('PRAGMA foreign_keys = OFF');

  // Truncate the table
  await db.execAsync(`DELETE FROM ${table}`);

  // Enable foreign key constraints
  await db.execAsync('PRAGMA foreign_keys = ON');
};

/**
 * add a new column to a table if it does not already exist
 * @param {Object} db - The datdabase connection object.
 * @param {string} table - the name of the table to add the column to.
 * @param {string} columnName - the name of the column to add.
 * @param {string} columnType - the type of the column to add.
 * @param {boolean} [nullable=true] - whether the column should be nullable. Defaults to true.
 * @param {string} [defaultValue=null] - optional default value for the column.
 * @returns {Promise<boolean>} A promise that resolves to true if the column was added, false if it already existed.
 */
const addNewColumn = async (
  db,
  table,
  columnName,
  columnType,
  nullable = true,
  defaultValue = null,
) => {
  // Check if the column already exists
  const rows = await db.getAllAsync(`PRAGMA table_info(${table})`);
  const existingColumn = rows.find((row) => row?.name === columnName);

  if (!existingColumn) {
    // Build the ALTER TABLE statement
    let alterStatement = `ALTER TABLE ${table} ADD COLUMN ${columnName} ${columnType}`;

    // Add NOT NULL constraint if the column is not nullable
    if (!nullable) {
      alterStatement += ' NOT NULL';
    }

    // Add DEFAULT clause if defaultValue is provided
    if (defaultValue !== null) {
      // For strings, wrap in quotes. For other types, use as is.
      const formattedDefault =
        typeof defaultValue === 'string' ? `'${defaultValue}'` : defaultValue;
      alterStatement += ` DEFAULT ${formattedDefault}`;
    }

    // Add the new column to the table
    await db.execAsync(alterStatement);
    return true;
  }
  return false;
};
/**
 * Drop a column to table if it exists
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to drop the column from.
 * @param {string} columnName - The name of the column to drop.
 * @returns {Promise<void>} A promise that resolves when the column has been dropped.
 * @throws {Error} If the column does not exist or if dropping the column fails.
 * @description SQLite does not support dropping columns directly, so this function creates a new table without the column,
 * copies the data over, drops the old table, and renames the new table to the original name.
 * This is a workaround for SQLite's limitations.
 */
const dropColumn = async (db, table, columnName) => {
  // Check if the column already exists
  const rows = await db.getAllAsync(`PRAGMA table_info(${table})`);
  const existingColumn = rows.find((row) => row?.name === columnName);
  // If the column does not exist, return early
  if (!existingColumn) {
    return;
  }

  if (existingColumn) {
    try {
      // SQLite does not support dropping columns directly, so we need to create a new table without the column
      // and copy the data over
      const tempTable = `${table}_temp`;
      await db.execAsync(`CREATE TABLE ${tempTable} AS SELECT * FROM ${table} WHERE 1=0;`);
      const columns = await db.getAllAsync(`PRAGMA table_info(${table})`);
      const columnNames = columns
        .filter((col) => col.name !== columnName)
        .map((col) => col.name)
        .join(', ');
      await db.execAsync(
        `INSERT INTO ${tempTable} (${columnNames}) SELECT ${columnNames} FROM ${table};`,
      );
      await db.execAsync(`DROP TABLE ${table};`);
      await db.execAsync(`ALTER TABLE ${tempTable} RENAME TO ${table};`);
    } catch (error) {
      throw new Error(`Error dropping column ${columnName} from table ${table}: ${error.message}`);
    }
  }
};

/**
 * Execute a function within a database transaction
 * @param {Object} db - The database connection object.
 * @param {Function} fn - The function to execute within the transaction.
 * @returns {Promise<any>} The result of the function execution.
 */
const withTransaction = async (db, fn) => {
  try {
    // BEGIN IMMEDIATE acquires the write lock up front so busy_timeout applies.
    // A deferred BEGIN can fail with SQLITE_BUSY on lock upgrade, which
    // busy_timeout does not retry in WAL mode.
    await db.execAsync('BEGIN IMMEDIATE TRANSACTION');
    const result = await fn(db);
    await db.execAsync('COMMIT');
    return result;
  } catch (error) {
    await db.execAsync('ROLLBACK');
    throw new Error(`Transaction failed: ${error.message}`);
  }
};

/**
 * Safely execute a query with proper error handling and parameter validation
 * @param {Object} db - The database connection object.
 * @param {string} query - The SQL query to execute.
 * @param {Array} params - The parameters for the query.
 * @param {string} operation - Description of the operation for error messages.
 * @returns {Promise<any>} The result of the query execution.
 */
const safeExecuteQuery = async (db, query, params = [], operation = 'query') => {
  try {
    // Validate that we have the right number of parameters
    const paramCount = (query.match(/\?/g) || []).length;
    if (params.length !== paramCount) {
      throw new Error(`Parameter count mismatch: expected ${paramCount}, got ${params.length}`);
    }

    const result = await db.getAllAsync(query, ...params);
    return result;
  } catch (error) {
    throw new Error(`Error executing ${operation}: ${error.message}`);
  }
};

/**
 * Safely get first row with proper error handling
 * @param {Object} db - The database connection object.
 * @param {string} query - The SQL query to execute.
 * @param {Array} params - The parameters for the query.
 * @param {string} operation - Description of the operation for error messages.
 * @returns {Promise<any>} The first row result.
 */
const safeGetFirstRow = async (db, query, params = [], operation = 'query') => {
  try {
    const paramCount = (query.match(/\?/g) || []).length;
    if (params.length !== paramCount) {
      throw new Error(`Parameter count mismatch: expected ${paramCount}, got ${params.length}`);
    }

    const result = await db.getFirstAsync(query, ...params);
    return result;
  } catch (error) {
    throw new Error(`Error executing ${operation}: ${error.message}`);
  }
};

/**
 * Execute multiple queries in a single transaction for better performance and consistency
 * @param {Object} db - The database connection object.
 * @param {Array} queries - Array of query objects with {query, params} structure.
 * @param {string} operation - Description of the batch operation.
 * @returns {Promise<Array>} Array of results from each query.
 */
const executeBatch = async (db, queries, operation = 'batch operation') =>
  withTransaction(db, async (transactionDb) => {
    const executeQueryInBatch = async (queryObj) => {
      const { query, params = [] } = queryObj;
      try {
        return await safeExecuteQuery(transactionDb, query, params, operation);
      } catch (error) {
        throw new Error(
          `Error in ${operation} - Query: ${query.substring(0, 50)}...: ${error.message}`,
        );
      }
    };

    return Promise.all(queries.map(executeQueryInBatch));
  });

/**
 * Safely execute multiple inserts with proper error handling
 * @param {Object} db - The database connection object.
 * @param {string} table - The table name.
 * @param {Array} records - Array of record objects to insert.
 * @returns {Promise<Array>} Array of inserted row IDs.
 */
const bulkInsert = async (db, table, records) => {
  if (!records || records.length === 0) {
    return [];
  }

  return withTransaction(db, async (transactionDb) => {
    const insertRecord = async (record) => {
      try {
        return await insertRow(transactionDb, table, record);
      } catch (error) {
        throw new Error(`Error in bulkInsert for table ${table}: ${error.message}`);
      }
    };

    return Promise.all(records.map(insertRecord));
  });
};

/**
 * Test query generation for debugging purposes
 * @param {string} table - The table name
 * @param {Object} conditions - The conditions object
 * @param {string} orderBy - The column to order by
 * @param {string} order - The order direction
 * @param {boolean} collateNoCase - Whether to use COLLATE NOCASE
 * @returns {Object} The generated query and parameters
 */
const testQueryGeneration = (
  table,
  conditions,
  orderBy = null,
  order = 'ASC',
  collateNoCase = false,
) => {
  const whereClause = Object.keys(conditions)
    .map((key) => (conditions[key] === null ? `${key} IS NULL` : `${key} = ?`))
    .join(' AND ');

  const params = Object.values(conditions).filter((val) => val !== null);

  let orderClause = '';
  if (orderBy) {
    const collateClause = collateNoCase ? ' COLLATE NOCASE' : '';
    orderClause = `ORDER BY ${orderBy}${collateClause} ${order}`;
  }

  const query = `SELECT * FROM ${table} WHERE ${whereClause} ${orderClause}`.trim();

  return { query, params };
};

const sql = {
  createTable,
  updateRow,
  deleteRow,
  getFirstRow,
  insertRow,
  getEachRow,
  getFilteredRows,
  executeQuery,
  dropTable,
  truncateTable,
  addNewColumn,
  dropColumn,
  withTransaction,
  safeExecuteQuery,
  safeGetFirstRow,
  executeBatch,
  bulkInsert,
  testQueryGeneration,
};

export default sql;
