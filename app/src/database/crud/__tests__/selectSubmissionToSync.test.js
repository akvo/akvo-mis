import crudDataPoints from '../crud-datapoints';
import sql from '../../sql';

jest.mock('../../sql', () => ({
  executeQuery: jest.fn(() => Promise.resolve([])),
  updateRow: jest.fn(() => Promise.resolve({ changes: 1 })),
}));

describe('crudDataPoints sync queries', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('selectSubmissionToSync filters strictly by submitted = 1 and syncedAt IS NULL', async () => {
    await crudDataPoints.selectSubmissionToSync({});
    expect(sql.executeQuery).toHaveBeenCalled();
    const [db, query] = sql.executeQuery.mock.calls[0];
    expect(db).toEqual({});
    expect(query).toContain('WHERE datapoints.syncedAt IS NULL');
    expect(query).toContain('AND datapoints.submitted = 1');
    expect(query).not.toContain('draftId IS NOT NULL');
    expect(query).not.toContain('sendToWeb = 1');
  });

  it('markSynced updates syncedAt without draftId', async () => {
    await crudDataPoints.markSynced({}, 12);
    expect(sql.updateRow).toHaveBeenCalledWith(
      {},
      'datapoints',
      { id: 12 },
      expect.objectContaining({
        syncedAt: expect.any(String),
      }),
    );
    const [, , , data] = sql.updateRow.mock.calls[0];
    expect(data.draftId).toBeUndefined();
  });
});
