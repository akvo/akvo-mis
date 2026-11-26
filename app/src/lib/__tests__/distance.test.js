import { parseGeo, geoFromAnswers, haversineMeters, formatDistance } from '../distance';

const trans = { distanceMeters: '{m} m away', distanceKm: '{km} km away' };

describe('parseGeo', () => {
  it('parses a valid "lat|lng" string', () => {
    expect(parseGeo('-8.676|115.49')).toEqual({ lat: -8.676, lng: 115.49 });
  });
  it('returns null for absent or malformed input', () => {
    expect(parseGeo(null)).toBeNull();
    expect(parseGeo('')).toBeNull();
    expect(parseGeo('not-a-coord')).toBeNull();
    expect(parseGeo('12')).toBeNull();
  });
});

describe('geoFromAnswers', () => {
  it('reads [lat,lng] from the geo question answer (object json)', () => {
    expect(geoFromAnswers({ 101: [23.27, 91.36], 102: 'x' }, ['101'])).toEqual({
      lat: 23.27,
      lng: 91.36,
    });
  });
  it('parses a stringified answers json with escaped quotes', () => {
    expect(geoFromAnswers('{"101":[1.5,2.5]}', ['101'])).toEqual({ lat: 1.5, lng: 2.5 });
  });
  it('returns null when no geo question has a valid point', () => {
    expect(geoFromAnswers({ 101: 'not-a-point' }, ['101'])).toBeNull();
    expect(geoFromAnswers({ 101: [1, 2] }, [])).toBeNull();
    expect(geoFromAnswers(null, ['101'])).toBeNull();
    expect(geoFromAnswers('not json', ['101'])).toBeNull();
  });
});

describe('haversineMeters', () => {
  it('is ~0 for identical points', () => {
    expect(haversineMeters({ lat: 1, lng: 1 }, { lat: 1, lng: 1 })).toBeCloseTo(0, 5);
  });
  it('matches a known short distance (~157 km per degree of latitude? no — ~111 km)', () => {
    // 1 degree of latitude ≈ 111.19 km
    const d = haversineMeters({ lat: 0, lng: 0 }, { lat: 1, lng: 0 });
    expect(d).toBeGreaterThan(111000);
    expect(d).toBeLessThan(111400);
  });
  it('returns null when a point is missing', () => {
    expect(haversineMeters(null, { lat: 1, lng: 1 })).toBeNull();
    expect(haversineMeters({ lat: 1, lng: 1 }, null)).toBeNull();
  });
});

describe('formatDistance', () => {
  it('shows whole metres below 1 km', () => {
    expect(formatDistance(120, trans)).toBe('120 m away');
    expect(formatDistance(999, trans)).toBe('999 m away');
  });
  it('shows one decimal from 1 to 10 km', () => {
    expect(formatDistance(2100, trans)).toBe('2.1 km away');
  });
  it('drops the decimal past ~10 km', () => {
    expect(formatDistance(18000, trans)).toBe('18 km away');
  });
  it('is empty for null/NaN', () => {
    expect(formatDistance(null, trans)).toBe('');
    expect(formatDistance(NaN, trans)).toBe('');
  });
});
