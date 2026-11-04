import { RadioButton, SelectionGroup } from 'hds-react';

/**
 * A generic dynamic radio group — one HDS `SelectionGroup` of `RadioButton`s
 * built from a caller-supplied option list. Extracted for `RequestThingPage`'s
 * HOUR-unit reservation flow (duration, then start time — two more dynamic
 * radio groups after the Availability page's static DAY/HOUR one), so all
 * three share one place that gets the two documented `SelectionGroup` quirks
 * right (frontend/CLAUDE.md) plus a third this codebase found the hard way:
 *
 * 1. Children must be one flat array, never a bare `.map()` result nested
 *    inside another expression — `SelectionGroup` doesn't flatten and the
 *    whole group silently renders with zero radios.
 * 2. Every child needs its own `id` (`SelectionGroup` re-wraps each in a
 *    `<div key={child.props.id}>`).
 * 3. That wrapper `id` must be DIFFERENT from the `RadioButton`'s own `id` —
 *    reusing it duplicates the id in the DOM, and `<label for>` then resolves
 *    to the empty wrapper, leaving every radio's accessible name blank. A
 *    bare radio-count assertion doesn't catch this; only a name-scoped query
 *    (`getByRole('radio', { name: … })`) does.
 *
 * `errorText` (optional) is passed to the `SelectionGroup`.
 */
export default function RadioOptionGroup({
  idPrefix,
  name,
  label,
  options,
  value,
  onChange,
  errorText,
}) {
  const fields = options.map((opt) => {
    const id = `${idPrefix}-${opt.value}`;
    return (
      <div key={id} id={`${id}-option`}>
        <RadioButton
          id={id}
          name={name}
          value={opt.value}
          label={opt.label}
          checked={value === opt.value}
          onChange={() => onChange(opt.value)}
        />
      </div>
    );
  });

  // `errorText` is HDS's own, shown under the group — a plain `div` HDS links
  // to nothing, so a screen reader won't hear it on its own. A caller that
  // sets it on submit should also move focus into the group (as
  // RequestThingPage does), which reads the question out.
  return (
    <SelectionGroup label={label} errorText={errorText}>
      {fields}
    </SelectionGroup>
  );
}
