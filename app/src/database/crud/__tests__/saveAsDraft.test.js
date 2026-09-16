import { crudDataPoints } from '../index';

const runAsync = jest.fn(() => Promise.resolve({ changes: 1 }));
const db = { runAsync };

describe('crudDataPoints.saveAsDraft', () => {
  beforeEach(() => {
    runAsync.mockClear();
  });

  it('hands the submission back as a draft', async () => {
    await crudDataPoints.saveAsDraft(db, 5);

    const [query, ...params] = runAsync.mock.calls[0];
    expect(query).toBe('UPDATE datapoints SET submitted = ? WHERE id = ?');
    expect(params).toEqual([0, 5]);
  });

  /**
   * The reason this is not `updateDataPoint(db, { id, submitted: 0 })`: that one writes
   * name, geo, duration, submittedAt and json unconditionally, so calling it with only an
   * id would null the submission it is meant to rescue. A refused submission is the last
   * copy of those answers.
   */
  it('writes only `submitted` — never touches the answers', async () => {
    await crudDataPoints.saveAsDraft(db, 5);

    const [query] = runAsync.mock.calls[0];
    ['json', 'name', 'geo', 'duration', 'submittedAt', 'syncedAt'].forEach((column) => {
      expect(query).not.toContain(column);
    });
  });

  /**
   * selectSubmissionToSync takes rows where submitted = 1 OR draftId IS NOT NULL OR
   * sendToWeb = 1. Clearing `submitted` is what drops a locally-born submission out of
   * that queue, which is what stops the retry loop.
   */
  it('leaves the row out of the sync queue by clearing submitted', async () => {
    await crudDataPoints.saveAsDraft(db, 5);

    const [, submittedValue] = runAsync.mock.calls[0];
    expect(submittedValue).toBe(0);
  });
});
