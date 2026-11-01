import { SelectionGroup, RadioButton } from 'hds-react';
import ApprovalNotice from './ApprovalNotice';

/**
 * The collection-mode radio group, shared by the Create and Edit forms.
 *
 * It used to be the same block twice: a hand-rolled `<fieldset>` with an
 * inline-styled `<legend>`, copied between the two pages with the id prefix and
 * the i18n key changed. HDS ships **`SelectionGroup`** for exactly this — a
 * fieldset whose legend is the group's accessible name — so the semantics that
 * block got right by hand now come from the design system, and its typography
 * comes with it instead of five inline declarations (DESIGN §1).
 *
 * **Which options exist is the caller's business, not this component's.** Create
 * offers what the deployment allows; Edit also offers the mode the collection is
 * already in, because the server only judges a *change* and a form that hid the
 * current answer would submit a wrong one. Neither rule belongs to the widget
 * that draws them. Both pages also pass `catalogue` — every mode the product
 * has — so `ApprovalNotice` can name what is missing and where to ask for it.
 *
 * **Two HDS SelectionGroup quirks decide the shape below** (see frontend/CLAUDE.md):
 * it does not flatten children, so the options are spread into one flat array
 * rather than nested as a `.map()`; and it re-wraps every child in a div keyed by
 * that child's **`id` prop**, so each wrapper carries an `id` it would not
 * otherwise need. Without the first, `isValidElement` rejects the nested array
 * and the radios silently vanish; without the second, React logs a missing-key
 * error for every option.
 */
export default function CollectionModeField({
  idPrefix,
  label,
  options,
  catalogue,
  value,
  onChange,
}) {
  const optionFields = options.map((opt) => {
    const id = `${idPrefix}-mode-${opt.value.toLowerCase()}`;
    return (
      // The label already holds the title and its explanation, so the wrapper is
      // only what SelectionGroup asks for (a child with an `id`, see above).
      <div key={id} id={`${id}-option`}>
        <RadioButton
          id={id}
          name={`${idPrefix}-mode`}
          value={opt.value}
          label={opt.label}
          checked={value === opt.value}
          onChange={() => onChange(opt.value)}
        />
      </div>
    );
  });

  return (
    <SelectionGroup label={label}>
      {[
        ...optionFields,
        <div key="approval" id={`${idPrefix}-mode-approval`}>
          <ApprovalNotice kind="collection_modes" catalogue={catalogue} />
        </div>,
      ]}
    </SelectionGroup>
  );
}
