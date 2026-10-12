import crudGeometryIndex from '../crud-geometry-index';
import sql from '../../sql';

jest.mock('../../sql', () => ({
  safeExecuteQuery: jest.fn(() => Promise.resolve([])),
  insertRow: jest.fn(() => Promise.resolve()),
}));

const bbox = { minLat: 0, maxLat: 1, minLon: 0, maxLon: 1 };

describe('crudGeometryIndex', () => {
  beforeEach(() => {
    sql.safeExecuteQuery.mockClear();
  });

  /**
   * A reopened draft used to save under a random session uuid, leaving index rows that still
   * name its datapointId. Excluding by uuid alone let the plot overlap itself through them.
   */
  it('excludes the plot by uuid and by the datapoints that carry it', async () => {
    await crudGeometryIndex.findOverlapCandidates(
      {},
      {
        formId: 1,
        questionId: 5,
        ...bbox,
        excludeUuid: 'self',
      },
    );
    const [, query, params] = sql.safeExecuteQuery.mock.calls[0];
    expect(query).toContain('uuid != ?');
    expect(query).toContain('datapointId NOT IN (SELECT id FROM datapoints WHERE uuid = ?)');
    expect(params.slice(-2)).toEqual(['self', 'self']);
  });

  it('sweeps rows of the same datapoint filed under another uuid when replacing', async () => {
    await crudGeometryIndex.replaceForDatapoint(
      {},
      {
        uuid: 'self',
        formId: 1,
        rows: [],
        datapointId: 7,
      },
    );
    expect(sql.safeExecuteQuery).toHaveBeenCalledWith(
      {},
      'DELETE FROM geometry_index WHERE formId = ? AND (uuid = ? OR datapointId = ?)',
      [1, 'self', 7],
      'geometryIndex.replaceForDatapoint.delete',
    );
  });
});
