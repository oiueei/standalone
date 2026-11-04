import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import ThingInfoRows from './ThingInfoRows';

// The row that only the deposit exists to protect:
// a RENT thing with a price AND a deposit must not read as one number.

describe('ThingInfoRows — deposit row', () => {
  test('never appears on a thing that carries no deposit', () => {
    render(<ThingInfoRows thing={{ type: 'GIFT_THING', fee: null }} isDateBased={false} />);
    expect(screen.queryByText(/deposit/i)).toBeNull();
  });

  test('shows the deposit amount, marked as returnable — not the price wording', () => {
    render(<ThingInfoRows thing={{ type: 'LEND_THING', deposit: '50.00' }} isDateBased={false} />);

    expect(screen.getByText('Deposit.')).toBeInTheDocument();
    expect(screen.getByText(/50\.00 €/)).toBeInTheDocument();
    expect(screen.getByText(/refundable/i)).toBeInTheDocument();
  });

  test('a RENT thing shows both rows, under two different labels', () => {
    render(
      <ThingInfoRows thing={{ type: 'RENT_THING', fee: '10.00', deposit: '50.00' }} isDateBased />
    );

    // "Price." and "Deposit." both present — the reader is never left to guess
    // whether 10 and 50 are one number or two separate promises.
    expect(screen.getByText('Price.')).toBeInTheDocument();
    expect(screen.getByText('Deposit.')).toBeInTheDocument();
    expect(screen.getByText(/10\.00 €/)).toBeInTheDocument();
    expect(screen.getByText(/50\.00 €/)).toBeInTheDocument();
  });
});

describe('ThingInfoRows — an amount of zero is not shown', () => {
  // The API sends the amounts as text, and "0.00" is truthy in JS.
  test.each([['0.00'], ['0'], [''], [null]])('no price and no deposit row for %j', (zero) => {
    render(
      <ThingInfoRows thing={{ type: 'LEND_THING', fee: zero, deposit: zero }} isDateBased={false} />
    );

    expect(screen.queryByText('Price.')).toBeNull();
    expect(screen.queryByText('Deposit.')).toBeNull();
  });

  test('a positive price and deposit are shown', () => {
    render(
      <ThingInfoRows
        thing={{ type: 'RENT_THING', fee: '5.00', deposit: '5.00' }}
        isDateBased={false}
      />
    );

    expect(screen.getByText('Price.')).toBeInTheDocument();
    expect(screen.getByText('Deposit.')).toBeInTheDocument();
  });
});

describe('ThingInfoRows — availability row', () => {
  // The thing's page and the card put the label in front of the row, so the value
  // can be the bare date; only the request page, whose notice does not show its
  // title, says the whole sentence.
  test('says the date alone after its label', () => {
    render(
      <ThingInfoRows
        thing={{ type: 'LEND_THING', available_today: false, next_available: '2026-11-09' }}
        isDateBased
      />
    );

    const label = screen.getByText('Availability.');
    expect(label.parentElement).toHaveTextContent(/^Availability\.\s*09\/11\/2026$/);
    expect(screen.queryByText(/First free day/)).toBeNull();
  });
});
