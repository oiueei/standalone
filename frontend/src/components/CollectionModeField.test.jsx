import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, test, expect } from 'vitest';

// `ApprovalNotice` asks the deployment what it allows; here it allows everything.
vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
}));

import CollectionModeField from './CollectionModeField';
import { settle } from '../test/settle';
import { apiFetch } from '../services/api';

/**
 * The collection-mode group's own contract — and, more to the point, **the
 * accessible wiring it now gets from HDS instead of by hand**.
 *
 * The block this replaced built its own `<fieldset>` and `<legend>`. Those are
 * what tell a screen-reader user that two radios are one question, and what
 * attach the question's text to them; they were visible in the JSX, so a change
 * that broke them would have been visible in review too. They now come from
 * `SelectionGroup`, which means an HDS upgrade can take them away silently — the
 * exact risk the project's HDS-version policy says the frontend suite has to
 * cover.
 *
 * The rest is the props contract two pages depend on. Nothing here mounts a page:
 * `collectionForm.test.jsx` and `EditCollectionPage.test.jsx` already drive the
 * radios through the real forms, which is what proves the wiring works in place.
 */

const MODES = [
  { value: 'PROPRIETARY', label: 'Just mine: Only you add things.' },
  { value: 'COMMUNITY', label: 'Shared: Members add their own things.' },
];

async function renderField(overrides = {}) {
  const onChange = vi.fn();
  const utils = render(
    <CollectionModeField
      idPrefix="create-collection"
      label="Who adds things?"
      options={MODES}
      catalogue={MODES}
      value="PROPRIETARY"
      onChange={onChange}
      {...overrides}
    />
  );
  // The notice's question is answered inside `act`, before the test looks.
  await settle(apiFetch);
  return { ...utils, onChange };
}

describe('the group is one question, not two loose radios', () => {
  test('the options sit in a group named by the label', async () => {
    const { container } = await renderField();

    // `<fieldset>` + `<legend>`: the semantics HDS supplies now. A radio that
    // announces "Shared" with no idea which question it answers is the
    // regression this catches.
    const group = container.querySelector('fieldset');
    expect(group).not.toBeNull();
    expect(group.querySelector('legend')).toHaveTextContent('Who adds things?');

    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);
    radios.forEach((radio) => expect(group.contains(radio)).toBe(true));
  });

  test('each radio is named by its own label, title and explanation together', async () => {
    await renderField();

    MODES.forEach((mode) => {
      // A screen reader reads this option's explanation as part of its name, and the
      // radio sets no `aria-describedby` that could point at another option's text.
      const radio = screen.getByRole('radio', { name: mode.label });
      expect(radio).not.toHaveAttribute('aria-describedby');
    });
  });

  test('the radios share one name, so picking one clears the other', async () => {
    await renderField();

    const names = screen.getAllByRole('radio').map((radio) => radio.getAttribute('name'));
    expect(new Set(names).size).toBe(1);
    expect(names[0]).toBe('create-collection-mode');
  });
});

describe('the props contract the two forms rely on', () => {
  test('the current value is the checked one', async () => {
    await renderField({ value: 'COMMUNITY' });

    expect(screen.getByRole('radio', { name: /^Shared:/ })).toBeChecked();
    expect(screen.getByRole('radio', { name: /^Just mine:/ })).not.toBeChecked();
  });

  test('picking an option reports its value, not an event', async () => {
    // The pages pass `handleModeChange`, which takes a mode string.
    const { onChange } = await renderField();

    fireEvent.click(screen.getByRole('radio', { name: /^Shared:/ }));

    expect(onChange).toHaveBeenCalledWith('COMMUNITY');
  });

  test('a narrowed deployment renders only the options it was given', async () => {
    // Withheld modes are dropped by the caller, never disabled here: an
    // unchoosable radio is noise, and ApprovalNotice is what names the absence.
    await renderField({ options: [MODES[0]], catalogue: MODES });

    expect(screen.getAllByRole('radio')).toHaveLength(1);
    expect(screen.queryByRole('radio', { name: /^Shared:/ })).toBeNull();
  });

  test('the ids follow the prefix, so two forms can render it on one page', async () => {
    const { container } = await renderField({ idPrefix: 'edit-collection' });

    expect(container.querySelector('#edit-collection-mode-proprietary')).not.toBeNull();
    expect(container.querySelector('#create-collection-mode-proprietary')).toBeNull();
  });
});
