/**
 * Pausing a thing between two days (both included). The server holds the rule; these
 * are the two things the page does with it on its own.
 */

/**
 * How many of a thing's bookings share a day with the pause `[from, until]` (ISO days,
 * both included), by the strict rule of `BookingPeriod.has_overlap`: a booking
 * `[start, end)` overlaps `[from, until + 1)` when it starts on or before `until` and
 * ends after `from`, so one that is back on the first day of the pause, or starts the
 * day after the last, does not count. Only the ones still standing (PENDING or
 * ACCEPTED) and with days (a gift's hold has none). Nothing for a pause that is not
 * (yet) a stretch.
 */
export function bookingsInPause(bookings, from, until) {
  if (!from || !until || from > until) return 0;
  return (bookings || []).filter(
    (b) =>
      (b.status === 'PENDING' || b.status === 'ACCEPTED') &&
      b.start_date &&
      b.end_date &&
      b.start_date <= until &&
      b.end_date > from
  ).length;
}
