import * as Sentry from '@sentry/react-native';
import sql from '../sql';
import crudUsers from './crud-users';

const tableName = 'jobs';
const jobsQuery = () => ({
  getActiveJob: async (db, type) => {
    try {
      const session = await crudUsers.getActiveUser(db);
      if (session?.id) {
        /**
         * Make sure the app only gets active jobs from current user
         */
        const where = { type, user: session.id };
        const nocase = false;
        const orderBy = 'createdAt';
        const rows = await sql.getFilteredRows(db, tableName, where, orderBy, 'DESC', nocase);
        return rows?.[0] || null;
      }
      return null;
    } catch (error) {
      // Still null, so callers keep treating this as "no active job" — but a dead
      // connection used to be indistinguishable from that, which let a whole
      // session fail invisibly until the follow-up insert threw instead.
      Sentry.captureMessage('[crudJobs] getActiveJob failed, treating as no active job');
      Sentry.captureException(error);
      return null;
    }
  },
  addJob: async (db, data = {}) => {
    try {
      const createdAt = new Date().toISOString()?.replace('T', ' ')?.split('.')?.[0] || null;
      return await sql.insertRow(db, tableName, {
        ...data,
        createdAt,
      });
    } catch (error) {
      return Promise.reject(error);
    }
  },
  updateJob: async (db, id, data) => {
    try {
      return await sql.updateRow(db, tableName, { id }, data);
    } catch {
      return null;
    }
  },
  deleteJob: async (db, id) => {
    try {
      return await sql.deleteRow(db, tableName, id);
    } catch {
      return null;
    }
  },
});

const crudJobs = jobsQuery();

export default crudJobs;
