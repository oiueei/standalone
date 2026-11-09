import { useEffect, useState } from 'react';
import { NumberInput } from 'hds-react';

/**
 * One bounded whole-number field. HDS `NumberInput` is controlled, so a field
 * bound straight to `Math.min(max, Math.max(min, n))` snaps to the bound on
 * every keystroke — you cannot clear "3" to type "5", and an empty field jumps
 * to 1. This keeps a local draft string so the field can be emptied, or briefly
 * hold a half-typed value, while editing.
 *
 * **The parent hears every whole number as it appears, not only on blur**.
 * It used to hear a value only when the field lost focus, so
 * anything that saves without a blur first — the +/- stepper, which moves focus
 * to its own button and never touches the input, or a keyboard Save — sent the
 * number the page had loaded while the field on screen showed the new one: "how
 * far ahead can they book" would not stay saved. A whole number is a real answer
 * the moment it exists, so it is committed at once, clamped to the bounds (an
 * out-of-range one snaps in view rather than sitting on screen as something the
 * page will not save). What stays a draft is exactly what is not yet an answer:
 * an empty field, a decimal, a lone minus sign — and blur settles those, with
 * the fallback for an empty one. The parent still only hears a number that
 * differs from the one it holds.
 */
export default function BoundedNumberInput({
  id,
  label,
  helperText,
  min,
  max,
  fallback,
  value,
  onChange,
  invalid,
  errorText,
}) {
  const [draft, setDraft] = useState(String(value));
  // Re-sync when the value arrives from outside — e.g. the Edit form finishing
  // its load. Our own commits set `draft` first, so this is then a no-op.
  useEffect(() => {
    setDraft(String(value));
  }, [value]);

  const commit = () => {
    const n = Math.round(Number(draft));
    const fixed =
      draft.trim() !== '' && Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback;
    setDraft(String(fixed));
    if (fixed !== value) onChange(fixed);
  };

  const handleChange = (e) => {
    const raw = e.target.value;
    // Not an answer yet (empty, "3.", "-"): keep typing, blur will settle it.
    if (!/^-?\d+$/.test(raw.trim())) {
      setDraft(raw);
      return;
    }
    const fixed = Math.min(max, Math.max(min, Number(raw)));
    setDraft(String(fixed));
    if (fixed !== value) onChange(fixed);
  };

  return (
    <NumberInput
      id={id}
      label={label}
      helperText={helperText}
      invalid={invalid}
      errorText={errorText}
      min={min}
      max={max}
      step={1}
      value={draft === '' ? '' : Number(draft)}
      onChange={handleChange}
      onBlur={commit}
    />
  );
}
