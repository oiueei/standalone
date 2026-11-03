import { describe, test, expect } from 'vitest';
import grid from '../test/hourlyGridParity.json';
import {
  dayBlocks,
  dayBookings,
  earliestStartMinutes,
  freeStartTimes,
  isHourlyPickupDisabled,
  parseLocalDate,
} from './rental';

/**
 * The request page and the server each decide which hourly starts exist: the
 * page offers them (`freeStartTimes`, `isHourlyPickupDisabled`), the server
 * accepts them (`Collection.reservation_hour_violation`, `has_overlap`,
 * `_day_has_a_free_hour`). Tested apart, each could drift from the other and
 * both suites stay green — a member offered a start the server refuses, or a
 * day greyed out that has room. These cases live in one JSON file that
 * `core/tests/unit/test_hourly_grid_parity.py` reads too, with the expected
 * starts worked out by hand in each case's note.
 */

const MONDAY = '2026-06-01';
const THE_DAY_AFTER = '2026-06-02';

const blockedPeriods = (bookings) =>
  bookings.map((range) =>
    range === null
      ? { start_date: MONDAY, end_date: THE_DAY_AFTER }
      : { start_date: MONDAY, end_date: THE_DAY_AFTER, start_time: range[0], end_time: range[1] }
  );

// The clock half-way through the given minute of that Monday, or the evening
// before when the case is not about today.
const clock = (minutes) =>
  minutes === null
    ? new Date(2026, 4, 31, 23, 0)
    : new Date(2026, 5, 1, Math.floor(minutes / 60), minutes % 60, 30);

describe.each(grid.cases)('the hourly grid: $name', (c) => {
  const openingHours = { 0: c.blocks };
  // What the server serves the page as taken: with several units, only where they
  // are all on (`served_periods`); with one, the bookings themselves.
  const served = c.served_periods ?? c.bookings;
  const day = parseLocalDate(MONDAY);
  const now = clock(c.now_minutes);

  test('the page offers exactly the starts the server accepts', () => {
    const starts = freeStartTimes(
      dayBlocks(openingHours, day),
      c.duration,
      dayBookings(blockedPeriods(served), MONDAY),
      c.min_minutes,
      earliestStartMinutes(MONDAY, now)
    );
    expect(starts).toEqual(c.starts);
  });

  test('the picker greys the day out exactly when the server finds no free slot', () => {
    const disabled = isHourlyPickupDisabled(day, {
      openingHours,
      closedDates: [],
      blockedPeriods: blockedPeriods(served),
      minMinutes: c.min_minutes,
      now,
    });
    expect(disabled).toBe(!c.day_has_a_free_slot);
  });
});
