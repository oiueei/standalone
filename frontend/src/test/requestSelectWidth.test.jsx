import { render } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { declarations } from './cssRules';
import ConstrainedRentalFields from '../components/request/ConstrainedRentalFields';
import DayReservationFields from '../components/request/DayReservationFields';
import OptionPicker from '../components/OptionPicker';

/**
 * HDS caps a Select's root at 420px, so on the request page the rental length stopped short
 * while the date under it filled the column. `App.css` already lifts the cap inside a
 * `.form-grid`; the request page's blocks live in a `.summary-grid`, so the rule has to name it
 * too. jsdom does no layout: what is pinned is the rule, and that the Select really is a direct
 * child of the `.summary-grid` the rule reaches (a wrapper in between would leave it capped).
 */
const SELECT = "div[class*='Select-module']";

describe('the request page’s dropdowns fill the column', () => {
  test('the stylesheet lifts HDS’s cap for a Select directly inside a .summary-grid', () => {
    expect(declarations(`.summary-grid > ${SELECT}`, 'max-width')).toEqual(['100%']);
  });

  test('the form’s own rule is still there', () => {
    expect(declarations(`.form-grid > ${SELECT}`, 'max-width')).toEqual(['100%']);
  });

  test('the rental length Select is a direct child of the .summary-grid', () => {
    const { container } = render(
      <ConstrainedRentalFields
        durations={[7, 14]}
        chosenDuration=""
        onDuration={vi.fn()}
        startDate=""
        onStartDate={vi.fn()}
        attempted={false}
        pickupDisabled={() => false}
      />
    );

    expect(container.querySelectorAll(`.summary-grid > ${SELECT}`)).toHaveLength(1);
    expect(container.querySelector('#request-duration').closest('.summary-grid')).not.toBeNull();
  });

  test('a day reservation’s length Select is one too, when there is a length to choose', () => {
    const { container } = render(
      <DayReservationFields
        thing={{ reservation_max_days: 3 }}
        chosenDuration=""
        onDuration={vi.fn()}
        startDate=""
        onStartDate={vi.fn()}
        attempted={false}
        pickupDisabled={() => false}
      />
    );

    expect(container.querySelectorAll(`.summary-grid > ${SELECT}`)).toHaveLength(1);
  });

  test('so is the dropdown an hourly reservation’s picker becomes past eight options', () => {
    const options = Array.from({ length: 12 }, (_, i) => ({
      value: String((i + 1) * 15),
      label: `${(i + 1) * 15} min`,
    }));
    const { container } = render(
      <div className="summary-grid">
        <OptionPicker
          idPrefix="reservation-duration"
          name="reservation-duration"
          label="Duration"
          placeholder="Choose"
          options={options}
          value=""
          onChange={vi.fn()}
        />
      </div>
    );

    expect(container.querySelectorAll(`.summary-grid > ${SELECT}`)).toHaveLength(1);
  });
});
