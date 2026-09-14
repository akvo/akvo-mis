/**
 * Regression for Sentry "TypeError: Cannot read property 'replace' of null"
 * in selectDataPointById (release 4.2.1).
 *
 * nginx rewrites /datapoints/<uuid>.json to /storage/datapoints/… and, with
 * no /storage location, a missing file falls through to the SPA fallback and
 * returns index.html with HTTP 200. The sync used to read `answers` off that
 * HTML string, get undefined, and save the datapoint with json = NULL; every
 * screen reading that row then crashed.
 */
import { crudDataPoints } from '../../database/crud';
import { parseAnswers } from '../../database/crud/crud-datapoints';
import sql from '../../database/sql';
import api from '../api';
import { downloadDatapointsJson } from '../sync-datapoints';

jest.mock('../../database/sql');
jest.mock('../api');

const SPA_HTML = '<!doctype html><html><head><title>Akvo MIS</title></head><body></body></html>';
const db = {};
const formCache = new Map([[42, { dbRecord: { id: 8, formId: 42 }, parsedGroups: [] }]]);
const info = {
  formId: 42,
  administrationId: 1,
  url: 'https://example.test/datapoints/0000-uuid.json',
  lastUpdated: '2026-09-14T00:00:00.000Z',
};

beforeEach(() => {
  sql.withTransaction.mockImplementation((_db, fn) => fn(_db));
  sql.getFirstRow.mockResolvedValue(null);
  sql.insertRow.mockResolvedValue(1);
});

describe('datapoint sync when the JSON file is missing on the server', () => {
  test('does not store a datapoint whose response has no answers', async () => {
    api.get.mockResolvedValue({ status: 200, data: SPA_HTML });

    await downloadDatapointsJson(db, info, 1, formCache);

    expect(sql.insertRow).not.toHaveBeenCalled();
  });

  test('still stores a datapoint whose response carries answers', async () => {
    api.get.mockResolvedValue({
      status: 200,
      data: { datapoint_name: 'Site', geolocation: null, answers: { 1: 'x' } },
    });

    await downloadDatapointsJson(db, info, 1, formCache);

    expect(sql.insertRow).toHaveBeenCalledTimes(1);
    expect(sql.insertRow.mock.calls[0][2].json).toBe('{"1":"x"}');
  });
});

describe('reading a datapoint row whose json is NULL or corrupt', () => {
  test('selectDataPointById returns null answers instead of throwing', async () => {
    sql.getFirstRow.mockResolvedValue({ id: 580, uuid: '0000-uuid', json: null });

    const row = await crudDataPoints.selectDataPointById(db, { id: 580 });

    expect(row.json).toBeNull();
  });

  test('parseAnswers tolerates NULL, corrupt text and the escaped-quote format', () => {
    expect(parseAnswers(null)).toBeNull();
    expect(parseAnswers('not json')).toBeNull();
    expect(parseAnswers(`{"1":"it''s"}`)).toEqual({ 1: "it's" });
  });
});
