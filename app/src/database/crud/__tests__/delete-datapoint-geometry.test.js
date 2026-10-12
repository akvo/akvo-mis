import crudDataPoints from '../crud-datapoints';
import sql from '../../sql';

jest.mock('../../sql', () => ({
  withTransaction: jest.fn((db, fn) => fn(db)),
  safeExecuteQuery: jest.fn(() => Promise.resolve()),
  deleteRow: jest.fn(() => Promise.resolve()),
}));

describe('deleteDataPoint', () => {
  /**
   * An orphaned index row is not harmless: GEO-007 reads a candidate whose answers are
   * gone as drift and refuses to validate the whole form until a resync.
   */
  it('removes the datapoint geometry index rows in the same transaction', async () => {
    await crudDataPoints.deleteDataPoint({}, 42);
    expect(sql.withTransaction).toHaveBeenCalled();
    expect(sql.safeExecuteQuery).toHaveBeenCalledWith(
      {},
      'DELETE FROM geometry_index WHERE datapointId = ?',
      [42],
      'datapoints.deleteDataPoint.geometryIndex',
    );
    expect(sql.deleteRow).toHaveBeenCalledWith({}, 'datapoints', 42);
  });
});
