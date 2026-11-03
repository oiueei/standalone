import { describe, test, expect } from 'vitest';
import { bookingsInPause } from './pause';

const booking = (start, end, status = 'ACCEPTED') => ({
  status,
  start_date: start,
  end_date: end,
});

describe('bookingsInPause', () => {
  // A pause from the 10th to the 12th, both included: [10, 13) as days.
  const count = (bookings) => bookingsInPause(bookings, '2026-06-10', '2026-06-12');

  test('counts a booking inside it, and one that starts before and ends after', () => {
    expect(count([booking('2026-06-11', '2026-06-12')])).toBe(1);
    expect(count([booking('2026-06-08', '2026-06-15')])).toBe(1);
  });

  test('counts one that ends on the second day and one that starts on the last', () => {
    expect(count([booking('2026-06-08', '2026-06-11')])).toBe(1);
    expect(count([booking('2026-06-12', '2026-06-14')])).toBe(1);
  });

  test('does not count one that is back on the first day of the pause', () => {
    expect(count([booking('2026-06-07', '2026-06-10')])).toBe(0);
  });

  test('does not count one that starts the day after the last', () => {
    expect(count([booking('2026-06-13', '2026-06-15')])).toBe(0);
  });

  test('counts a one-day pause against a booking of that day only', () => {
    const one = (bookings) => bookingsInPause(bookings, '2026-06-10', '2026-06-10');
    expect(one([booking('2026-06-10', '2026-06-11')])).toBe(1);
    expect(one([booking('2026-06-09', '2026-06-10')])).toBe(0);
    expect(one([booking('2026-06-11', '2026-06-12')])).toBe(0);
  });

  test('counts only what is still standing', () => {
    expect(
      count([
        booking('2026-06-11', '2026-06-12', 'PENDING'),
        booking('2026-06-11', '2026-06-12', 'ACCEPTED'),
        booking('2026-06-11', '2026-06-12', 'CANCELLED'),
        booking('2026-06-11', '2026-06-12', 'REJECTED'),
        booking('2026-06-11', '2026-06-12', 'EXPIRED'),
      ])
    ).toBe(2);
  });

  test('ignores a booking with no days', () => {
    expect(count([{ status: 'PENDING', start_date: null, end_date: null }])).toBe(0);
  });

  test.each([
    ['no first day', '', '2026-06-12'],
    ['no last day', '2026-06-10', ''],
    ['a last day before the first', '2026-06-12', '2026-06-10'],
  ])('counts nothing for %s', (_, from, until) => {
    expect(bookingsInPause([booking('2026-06-10', '2026-06-13')], from, until)).toBe(0);
  });

  test('counts nothing for no bookings at all', () => {
    expect(bookingsInPause(undefined, '2026-06-10', '2026-06-12')).toBe(0);
    expect(bookingsInPause(null, '2026-06-10', '2026-06-12')).toBe(0);
  });
});
