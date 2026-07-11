import { describe, test, expect, beforeAll, afterAll, vi } from 'vitest';
import {
  jsToPyWeekday,
  parseLocalDate,
  addDays,
  toISODate,
  weekdayAllowed,
  isDateBlocked,
  isPickupBlocked,
  isPickupDisabled,
  derivedReturnDate,
} from './rental';

// Run in a UTC-negative timezone so a regression to UTC date parsing
// (new Date('YYYY-MM-DD') → UTC midnight → previous local day) is actually caught.
beforeAll(() => {
  vi.stubEnv('TZ', 'America/New_York');
});
afterAll(() => {
  vi.unstubAllEnvs();
});

// Anchor: 2024-01-01 is a Monday, so 2024-01-03 is a Wednesday (Python weekday 2)
// and 2024-01-04 a Thursday (3).

describe('jsToPyWeekday', () => {
  test('maps JS Sunday-first to Python Monday-first', () => {
    expect(jsToPyWeekday(0)).toBe(6); // Sunday
    expect(jsToPyWeekday(1)).toBe(0); // Monday
    expect(jsToPyWeekday(3)).toBe(2); // Wednesday
    expect(jsToPyWeekday(6)).toBe(5); // Saturday
  });
});

describe('parseLocalDate', () => {
  test('parses a YYYY-MM-DD string on the intended LOCAL day, not UTC', () => {
    const d = parseLocalDate('2024-01-03');
    expect(d.getFullYear()).toBe(2024);
    expect(d.getMonth()).toBe(0);
    expect(d.getDate()).toBe(3); // would be 2 under the UTC-parse bug in this TZ
    expect(d.getTime()).toBe(new Date(2024, 0, 3).getTime());
  });

  test('normalises a Date to local midnight without shifting the day', () => {
    const d = parseLocalDate(new Date(2024, 0, 3, 12, 30));
    expect(d.getDate()).toBe(3);
    expect(d.getHours()).toBe(0);
  });
});

describe('addDays / toISODate / derivedReturnDate', () => {
  test('addDays keeps the return on the same weekday a week later', () => {
    // 2024-01-03 is a Wednesday; +7 days is the next Wednesday, not one short.
    expect(toISODate(addDays('2024-01-03', 7))).toBe('2024-01-10');
    expect(addDays('2024-01-03', 7).getDay()).toBe(3); // still Wednesday
  });

  test('derivedReturnDate returns pickup + length as an ISO string', () => {
    expect(derivedReturnDate('2024-01-03', 7)).toBe('2024-01-10');
    expect(derivedReturnDate('2024-01-03', '1')).toBe('2024-01-04');
  });

  test('toISODate uses local components', () => {
    expect(toISODate(new Date(2024, 0, 3))).toBe('2024-01-03');
  });
});

describe('weekdayAllowed', () => {
  test('is unrestricted when no weekdays are configured', () => {
    expect(weekdayAllowed('2024-01-04', [])).toBe(true);
  });
  test('allows only the configured Python weekdays', () => {
    expect(weekdayAllowed('2024-01-03', [2])).toBe(true); // Wednesday
    expect(weekdayAllowed('2024-01-04', [2])).toBe(false); // Thursday
  });
});

describe('isDateBlocked', () => {
  const periods = [{ start_date: '2024-01-03', end_date: '2024-01-05' }];
  test('is inclusive of both ends', () => {
    expect(isDateBlocked('2024-01-03', periods)).toBe(true);
    expect(isDateBlocked('2024-01-05', periods)).toBe(true);
  });
  test('is false outside the range', () => {
    expect(isDateBlocked('2024-01-02', periods)).toBe(false);
    expect(isDateBlocked('2024-01-06', periods)).toBe(false);
  });
  test('accepts a Date as well as a string', () => {
    expect(isDateBlocked(new Date(2024, 0, 4), periods)).toBe(true);
  });
});

describe('isPickupBlocked', () => {
  const periods = [{ start_date: '2024-01-03', end_date: '2024-01-05' }];
  test('blocks pickup on the start day and interior days', () => {
    expect(isPickupBlocked('2024-01-03', periods)).toBe(true);
    expect(isPickupBlocked('2024-01-04', periods)).toBe(true);
  });
  test('allows pickup on the return day (end) — back-to-back handover', () => {
    expect(isPickupBlocked('2024-01-05', periods)).toBe(false);
  });
  test('is false outside the range', () => {
    expect(isPickupBlocked('2024-01-02', periods)).toBe(false);
    expect(isPickupBlocked('2024-01-06', periods)).toBe(false);
  });
});

describe('isPickupDisabled', () => {
  const base = { rentalWeekdays: [2], blockedPeriods: [], duration: '' };
  test('disables a pickup on a disallowed weekday', () => {
    expect(isPickupDisabled('2024-01-04', base)).toBe(true); // Thursday
  });
  test('allows a valid pickup weekday with no duration chosen', () => {
    expect(isPickupDisabled('2024-01-03', base)).toBe(false); // Wednesday
  });
  test('allows a length whose return lands on an allowed weekday', () => {
    // Wed + 7 = next Wed, both allowed.
    expect(isPickupDisabled('2024-01-03', { ...base, duration: '7' })).toBe(false);
  });
  test('disables a length whose return lands on a disallowed weekday', () => {
    // Wed + 1 = Thursday, not allowed.
    expect(isPickupDisabled('2024-01-03', { ...base, duration: '1' })).toBe(true);
  });
  test('disables when any day in the pickup→return range is booked', () => {
    const opts = {
      rentalWeekdays: [],
      blockedPeriods: [{ start_date: '2024-01-06', end_date: '2024-01-06' }],
      duration: '7',
    };
    expect(isPickupDisabled('2024-01-03', opts)).toBe(true); // 06 falls inside [03..10]
  });
  test('allows a chained Wednesday→Wednesday pickup on an existing return day', () => {
    // Existing 7-day rental [Wed 01-03 → Wed 01-10]; a new week picked up on the
    // return day 01-10 (also a Wednesday) is now valid — strict overlap only.
    const opts = {
      rentalWeekdays: [2], // Wednesday only
      blockedPeriods: [{ start_date: '2024-01-03', end_date: '2024-01-10' }],
      duration: '7',
    };
    expect(isPickupDisabled('2024-01-10', opts)).toBe(false);
  });
  test('still disables a pickup interior to an existing booking', () => {
    const opts = {
      rentalWeekdays: [],
      blockedPeriods: [{ start_date: '2024-01-03', end_date: '2024-01-10' }],
      duration: '7',
    };
    expect(isPickupDisabled('2024-01-08', opts)).toBe(true); // 08 is interior to [03..10)
  });
});
