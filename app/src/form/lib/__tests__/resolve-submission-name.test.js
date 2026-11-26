import { resolveSubmissionName, formatShortDateTime } from '../index';

describe('formatShortDateTime', () => {
  it('formats as YYYY-MM-DD HH:mm with zero padding (local time)', () => {
    expect(formatShortDateTime(new Date(2026, 0, 5, 9, 7))).toBe('2026-01-05 09:07');
    expect(formatShortDateTime(new Date(2026, 10, 26, 16, 23))).toBe('2026-11-26 16:23');
  });
});

describe('resolveSubmissionName (APP-598)', () => {
  const untitledText = 'Untitled';

  it('uses the generated name when present', () => {
    const name = resolveSubmissionName({
      dpName: 'Kasese Well 07',
      isMonitoring: true,
      parentName: 'Parent Project',
      untitledText,
    });
    expect(name).toBe('Kasese Well 07');
  });

  it('trims a whitespace-padded generated name', () => {
    const name = resolveSubmissionName({
      dpName: '  My Name  ',
      isMonitoring: false,
      parentName: null,
      untitledText,
    });
    expect(name).toBe('My Name');
  });

  it('borrows parent name + datetime for an unnamed monitoring submission', () => {
    const name = resolveSubmissionName({
      dpName: '',
      isMonitoring: true,
      parentName: 'Kasese Well 07',
      untitledText,
    });
    expect(name).toMatch(/^Kasese Well 07 — \d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  });

  it('falls back to untitled for an unnamed registration submission', () => {
    const name = resolveSubmissionName({
      dpName: '',
      isMonitoring: false,
      parentName: null,
      untitledText,
    });
    expect(name).toBe('Untitled');
  });

  it('falls back to untitled for unnamed monitoring with no parent name', () => {
    const name = resolveSubmissionName({
      dpName: null,
      isMonitoring: true,
      parentName: undefined,
      untitledText,
    });
    expect(name).toBe('Untitled');
  });
});
