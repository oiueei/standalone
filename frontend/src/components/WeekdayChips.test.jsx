import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import WeekdayChips from './WeekdayChips';
import declarePalette from '../test/declarePalette';

// WeekdayChips owns the weekday toggle logic for BOTH rules blocks (rental
// pickup/return days, reservation open days). A value that leaves here in the
// wrong shape or the wrong numbering silently narrows — or wrongly widens —
// every booking in the collection. The selected-chip colours are the other
// promise: they must stay legible on every theeeme.

function renderChips(over = {}) {
  const props = {
    labelId: 'x-weekdays-label',
    labelKey: 'rental.weekdaysLabel',
    helperKey: 'rental.weekdaysHelper',
    weekdays: [],
    setWeekdays: vi.fn(),
    ...over,
  };
  return { ...render(<WeekdayChips {...props} />), props };
}

// Python weekday numbering (0=Mon … 6=Sun) — what the backend stores.
const chip = (name) => screen.getByRole('button', { name });

describe('WeekdayChips — the weekday toggle', () => {
  test('renders a labelled group with one chip per weekday, each named in full', () => {
    renderChips();
    // The visible face is a single narrow letter, so the full name has to ride
    // along as the accessible name for a screen reader.
    const group = screen.getByRole('group', { name: 'Pickup / return days' });
    expect(group).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Monday' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sunday' })).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(7);
  });

  test('selecting Monday stores 0 — Python numbering, not JS getDay()', () => {
    // JS getDay() calls Sunday 0; the backend calls Monday 0. Getting this
    // backwards shifts every allowed day by one.
    const { props } = renderChips();
    fireEvent.click(chip('Monday'));
    expect(props.setWeekdays).toHaveBeenCalledWith([0]);
  });

  test('selecting Sunday stores 6, the last Python weekday', () => {
    const { props } = renderChips();
    fireEvent.click(chip('Sunday'));
    expect(props.setWeekdays).toHaveBeenCalledWith([6]);
  });

  test('a selected day reports itself pressed; an unselected one does not', () => {
    renderChips({ weekdays: [0, 4] });
    expect(chip('Monday')).toHaveAttribute('aria-pressed', 'true');
    expect(chip('Friday')).toHaveAttribute('aria-pressed', 'true');
    expect(chip('Tuesday')).toHaveAttribute('aria-pressed', 'false');
  });

  test('clicking a selected chip removes just that day', () => {
    const { props } = renderChips({ weekdays: [0, 2, 4] });
    fireEvent.click(chip('Wednesday'));
    expect(props.setWeekdays).toHaveBeenCalledWith([0, 4]);
  });

  test('days come back sorted however they were clicked', () => {
    // Harmless to the backend comparison, but an unsorted list makes the saved
    // value churn on every edit.
    const { props } = renderChips({ weekdays: [4] });
    fireEvent.click(chip('Monday'));
    expect(props.setWeekdays).toHaveBeenCalledWith([0, 4]);
  });

  test('the label and helper come from the keys the caller passes', () => {
    renderChips({ labelKey: 'reservation.weekdaysLabel', helperKey: 'reservation.weekdaysHelper' });
    expect(screen.getByRole('group', { name: 'Days open for reservations' })).toBeInTheDocument();
    expect(screen.getByText(/A reservation can't span a closed day\./)).toBeInTheDocument();
  });
});

describe('WeekdayChips — the selected chip stays legible on every theeeme', () => {
  test('a selected chip pairs color_06 text with the color_01 fill, never a hardcoded white', () => {
    // color_01 is a light accent on 10 of the 12 curated palettes (engel,
    // summer, gold, copper, fog, metro, suomenlinna…), so white text on it
    // drops well below WCAG AA — engel is 1.22:1. color_06-on-color_01 is the
    // primary-button pairing, which paletteContrast.test.js already pins at
    // >= 4.5:1 for all 12.
    declarePalette({ color_01: 'engel', color_06: 'black' });
    renderChips({ weekdays: [2] });
    expect(chip('Wednesday')).toHaveStyle({
      backgroundColor: 'var(--color-engel)',
      color: 'var(--color-black)',
    });
  });

  test('with a palette that has no color_06 the chip is left to the CSS default (white on black-90)', () => {
    // The fallback only has to read on a dark surface, which the App.css default
    // (.weekday-chip.selected → black-90 fill) guarantees; the inline white here
    // matches it rather than fighting it.
    declarePalette({ color_01: 'bus' });
    renderChips({ weekdays: [2] });
    expect(chip('Wednesday')).toHaveStyle({
      backgroundColor: 'var(--color-bus)',
      color: 'var(--color-white)',
    });
  });

  test('an unselected chip carries no inline colour at all', () => {
    declarePalette({ color_01: 'engel', color_06: 'black' });
    renderChips({ weekdays: [] });
    expect(chip('Wednesday')).not.toHaveAttribute('style');
  });
});
