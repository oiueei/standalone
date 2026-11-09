import { useEffect, useState } from 'react';
import { TextArea } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { openingHoursWeek } from '../utils/rental';
import { errorKey, translateError } from '../utils/errorKey';

/**
 * The weekly opening-hours editor for an HOUR-unit reservations collection:
 * one raw-JSON `TextArea`, matching `Collection.opening_hours` exactly —
 * `{"0".."6": [["HH:MM","HH:MM"], ...]}`, Python weekday() numbering
 * (0=Mon…6=Sun) as string keys, a day absent or given `[]` closed. Deliberate,
 * after trying the per-day block editor this replaced: typing or
 * pasting the JSON directly is faster than clicking through seven fieldsets
 * for a schedule you already have written down somewhere.
 *
 * Local `draft` mirrors `BoundedNumberInput`'s pattern — the owner can type a
 * momentarily unbalanced brace without the field fighting them — but unlike
 * that field (and unlike `ClosedDatesField`, which forwards its raw string
 * untouched), this one *must* parse on the way out: `opening_hours` is a
 * nested JSON object in the request body, not a string, so an unparseable
 * draft simply cannot become a valid `onChange` call. A parse failure keeps
 * the parent's last-known-good value and shows an inline error instead of
 * ever forwarding one — the deeper *shape* checks (day keys, HH:MM format,
 * overlap) still stay the backend's job, same as everywhere else in these
 * forms (`_validate_opening_hours`, surfaced as its own 400 via Toast).
 *
 * **The re-sync compares content, not the `value` reference, and does it
 * during render — not in an effect.** `BoundedNumberInput` can key its resync
 * effect on the bare reference because its `value` is a number — equal
 * content IS equal reference there. This field's `value` is an object, so a
 * parent that ever passes `openingHours={form.opening_hours || {}}` (a fresh
 * `{}` literal on every render whenever the field is unset) would fire an
 * effect keyed on `[value]` on every unrelated keystroke elsewhere in the
 * form and wipe whatever JSON the owner was mid-typing back to `{}` — real
 * data loss in a field people paste a whole week's schedule into. Both
 * current call sites happen to pass a referentially-stable `useState` object,
 * so this was never reachable in production, but the component's own
 * contract shouldn't have silently depended on that.
 *
 * `syncedJson` holds the content we last synced FROM `value` (starting at the
 * initial one, before any typing). This is React's own documented pattern for
 * "adjusting state when a prop changes" — https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
 * — a plain `if` in the render body, not a `useEffect`: calling `setState`
 * conditionally inside an effect (which an earlier version of this fix did)
 * is itself the anti-pattern `react-hooks/set-state-in-effect` flags, since it
 * commits the stale draft to the screen first and only corrects it a tick
 * later. Doing the comparison during render lets React re-render with the
 * synced draft before anything paints, and it terminates the same way: once
 * `draft`/`syncedJson` reflect `value`, the condition is false on the very
 * next render, so there is no loop. A re-sync also clears any error: the draft
 * it installs is the parent's own value, valid by construction.
 *
 * **`onValidityChange(valid)` tells the page whether the draft on screen is
 * one this field could hand over.** Keeping the last-known-good value is only
 * half of not losing work: the page's Save used to send that stale value and
 * navigate away, taking the inline error with it — so an owner whose paste had
 * a trailing comma believed a schedule was saved that never was (found in
 * review, 2026-09-18). The page refuses to submit while this reports `false`.
 * It mirrors `error` from an effect rather than being called from `commit`
 * alone, since the error also clears on a re-sync (during render, where a
 * parent's setter can't be called). The cleanup reports `true` on unmount: an
 * unmounted field has no draft on screen to refuse, and when it mounts again it
 * shows the last good value, which is what the parent holds. Nothing on the
 * Availability page folds this field away, so the only unmount is the owner
 * leaving "By hour" (and the refusal goes with the draft it was about; pinned in
 * `CollectionAvailabilityPage.test.jsx`). Pass a stable function (a state
 * setter): the effect re-runs whenever its identity changes.
 */
const noop = () => {};

// The format is explained by a notice the page puts above the field, not by a line under it.

export default function OpeningHoursField({
  id,
  value = {},
  onChange = noop,
  onValidityChange = noop,
}) {
  const { t, i18n } = useTranslation();
  const [draft, setDraft] = useState(() => JSON.stringify(value));
  const [error, setError] = useState('');
  const [syncedJson, setSyncedJson] = useState(() => JSON.stringify(value));

  const incomingJson = JSON.stringify(value);
  if (incomingJson !== syncedJson) {
    setSyncedJson(incomingJson);
    setDraft(incomingJson);
    setError('');
  }

  useEffect(() => {
    onValidityChange(!error);
    return () => onValidityChange(true);
  }, [error, onValidityChange]);

  const commit = () => {
    if (draft.trim() === '') {
      setError('');
      if (Object.keys(value).length) onChange({});
      return;
    }
    let parsed;
    try {
      parsed = JSON.parse(draft);
    } catch {
      setError(errorKey('openingHours.invalidJson'));
      return;
    }
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      setError(errorKey('openingHours.invalidJson'));
      return;
    }
    setError('');
    onChange(parsed);
  };

  // What the saved value says, in words: the owner checks the week without
  // reading the JSON back. It follows `value` — what Save would send — so a
  // draft that does not parse leaves the last good week on screen, under the
  // field's own error. Nothing is shown while no day is set.
  const week = Object.keys(value).length ? openingHoursWeek(value, i18n.language) : null;

  return (
    <>
      <TextArea
        id={id}
        label={t('openingHours.label')}
        required
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        invalid={!!error}
        errorText={translateError(t, error)}
      />
      {week && (
        <div className="opening-hours-preview">
          <p className="text-muted" id={`${id}-preview-label`}>
            {t('openingHours.previewLabel')}
          </p>
          <ul aria-labelledby={`${id}-preview-label`}>
            {week.map(({ day, name, ranges }) => (
              <li key={day}>
                <span className="opening-hours-preview-day">{name}</span>{' '}
                {ranges.length ? ranges.join(', ') : t('openingHours.closed')}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
