import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import BoundedNumberInput from './BoundedNumberInput';

// The number fields decide what a member can book: the longest span, how far ahead, how many
// at once. They are the fiddly part — HDS NumberInput is controlled, so a naive clamp snaps
// the field on every keystroke.

function renderField(over = {}) {
  const props = {
    id: 'days',
    label: 'Longest reservation (days)',
    min: 1,
    max: 7,
    fallback: 1,
    value: 3,
    onChange: vi.fn(),
    ...over,
  };
  return { ...render(<BoundedNumberInput {...props} />), props };
}

// HDS NumberInput wraps the numeric <input> in a role="group", so the label text matches
// twice — query the input by its spinbutton role.
const field = () => screen.getByRole('spinbutton', { name: 'Longest reservation (days)' });

describe('BoundedNumberInput', () => {
  test('shows the stored value', () => {
    renderField({ value: 5 });
    expect(field()).toHaveValue(5);
  });

  test('the field can be emptied mid-edit without snapping back to the minimum', () => {
    // The bug: value bound straight to Math.max(1, Number('')) === 1, so the field jumped to 1
    // the moment you cleared it to retype.
    const { props } = renderField();
    fireEvent.change(field(), { target: { value: '' } });
    expect(field()).toHaveValue(null); // genuinely empty, not 1
    // …and an empty field is not an answer, so the parent hears nothing.
    expect(props.onChange).not.toHaveBeenCalled();
  });

  test('a whole number is committed to the parent as soon as it is typed — no blur needed', () => {
    // The parent used to hear a number only when the field lost focus, so a save that came
    // without one sent the loaded value while the screen showed the new one. There is no
    // `fireEvent.blur` below: that is the whole point.
    const { props } = renderField();
    fireEvent.change(field(), { target: { value: '5' } });
    expect(props.onChange).toHaveBeenCalledWith(5);
    expect(field()).toHaveValue(5);
  });

  test('the + stepper reaches the parent with no focus change at all', () => {
    // The buttons beside the number take focus themselves and never touch the input, so its
    // blur never fires: whatever they change has to reach the parent on its own.
    const { props } = renderField({ value: 3 });
    const stepUp = field().closest('[role="group"]').querySelectorAll('button')[1];

    fireEvent.click(stepUp);

    expect(props.onChange).toHaveBeenCalledWith(4);
    expect(field()).toHaveValue(4);
  });

  test('a value above the ceiling is clamped to it at once, and the field shows the clamp', () => {
    const { props } = renderField();
    fireEvent.change(field(), { target: { value: '99' } });
    expect(props.onChange).toHaveBeenCalledWith(7);
    expect(field()).toHaveValue(7);
  });

  test('a half-typed value is a draft — not committed, and settled by blur', () => {
    const { props } = renderField();
    fireEvent.change(field(), { target: { value: '4.5' } });
    expect(props.onChange).not.toHaveBeenCalled();
    fireEvent.blur(field());
    expect(props.onChange).toHaveBeenCalledWith(5);
  });

  test('clearing the field commits the fallback on blur, not an empty payload', () => {
    const { props } = renderField({ value: 200, max: 365, fallback: 90 });
    fireEvent.change(field(), { target: { value: '' } });
    fireEvent.blur(field());
    expect(props.onChange).toHaveBeenCalledWith(90);
    expect(field()).toHaveValue(90);
  });

  test('clamps to the bounds of its own range', () => {
    const { props } = renderField({ value: 25, min: 1, max: 50, fallback: 10 });
    expect(field()).toHaveValue(25);

    fireEvent.change(field(), { target: { value: '99' } });
    fireEvent.blur(field());
    expect(props.onChange).toHaveBeenCalledWith(50);

    fireEvent.change(field(), { target: { value: '0' } });
    expect(props.onChange).toHaveBeenLastCalledWith(1);
  });

  test('a value equal to what the parent already holds is not re-emitted on blur', () => {
    const { props } = renderField({ value: 3 });
    fireEvent.blur(field());
    expect(props.onChange).not.toHaveBeenCalled();
  });

  test('a value that changed from outside the component re-syncs the field', () => {
    const { rerender, props } = renderField({ value: 3 });
    expect(field()).toHaveValue(3);
    rerender(<BoundedNumberInput {...props} value={6} />);
    expect(field()).toHaveValue(6);
  });
});
