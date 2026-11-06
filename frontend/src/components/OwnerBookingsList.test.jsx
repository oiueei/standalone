import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import OwnerBookingsList from './OwnerBookingsList';

const wholeDayBooking = {
  code: 'BKG001',
  status: 'ACCEPTED',
  start_date: '2026-10-05',
  end_date: '2026-10-06',
};

const hourlyBooking = {
  code: 'BKG002',
  status: 'ACCEPTED',
  start_date: '2026-10-05',
  end_date: '2026-10-06',
  start_time: '11:00:00',
  end_time: '13:00:00',
};

describe('OwnerBookingsList', () => {
  test('renders nothing for a non-owner', () => {
    const { container } = render(
      <OwnerBookingsList bookings={[wholeDayBooking]} activePendingCode={null} isOwner={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  test('a whole-day booking shows a date range', () => {
    render(
      <OwnerBookingsList bookings={[wholeDayBooking]} activePendingCode={null} isOwner={true} />
    );
    expect(screen.getByText(/05\/10\/2026 — 06\/10\/2026/)).toBeInTheDocument();
  });

  test('an HOUR-unit reservation shows the date once and both times, not the day-based end_date', () => {
    render(
      <OwnerBookingsList bookings={[hourlyBooking]} activePendingCode={null} isOwner={true} />
    );
    expect(screen.getByText(/05\/10\/2026, 11:00–13:00/)).toBeInTheDocument();
    expect(screen.queryByText(/06\/10\/2026/)).toBeNull();
  });

  test('on a reservation card a one-day booking is that one day — the card supplies the type', () => {
    // Calendar rows carry no thing_type; without the card's own type the day
    // the space frees up (the 6th) listed as a second reserved day.
    render(
      <OwnerBookingsList
        bookings={[wholeDayBooking]}
        activePendingCode={null}
        isOwner={true}
        thingType="RESERVE_THING"
      />
    );
    expect(screen.getByText(/05\/10\/2026/)).toBeInTheDocument();
    expect(screen.queryByText(/06\/10\/2026/)).toBeNull();
  });
});

describe('OwnerBookingsList — a request for several', () => {
  const several = { ...wholeDayBooking, requester_name: 'Lele', quantity: 4 };

  test('says how many of the thing, before who and when', () => {
    render(
      <OwnerBookingsList
        bookings={[several]}
        activePendingCode={null}
        isOwner={true}
        thingHeadline="Arduino kit"
      />
    );

    expect(screen.getByText(/^4 × Arduino kit\. Lele\./)).toBeInTheDocument();
  });

  test.each([
    ['one', { ...several, quantity: 1 }],
    ['none said', { ...several, quantity: undefined }],
  ])('says nothing of it with %s', (_, booking) => {
    render(
      <OwnerBookingsList
        bookings={[booking]}
        activePendingCode={null}
        isOwner={true}
        thingHeadline="Arduino kit"
      />
    );

    expect(screen.queryByText(/×/)).toBeNull();
  });

  test('resolves a headline written in several languages', () => {
    render(
      <OwnerBookingsList
        bookings={[several]}
        activePendingCode={null}
        isOwner={true}
        thingHeadline='{"en":"Arduino kit","es":"Kit de Arduino"}'
      />
    );

    expect(screen.getByText(/4 × Arduino kit/)).toBeInTheDocument();
  });
});
