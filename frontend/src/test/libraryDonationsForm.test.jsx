import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

expect.extend(toHaveNoViolations);
window.scrollTo = vi.fn();

vi.mock('../services/api', async (orig) => ({
  ...(await orig()),
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));
vi.mock('../utils/externalForms', () => ({ externalFormUrl: () => null }));
vi.mock('../deployment', async (orig) => ({ ...(await orig()), requestAccessPaths: {} }));

import { apiFetch } from '../services/api';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import { dropHdsStyles } from './dropHdsStyles';
import { settle } from './settle';
import en from '../i18n/locales/en.json';

/**
 * A library's donations on the General page: the switch, and the instructions field that
 * exists only while the switch is on. Never in a stall, a shed or the creation form.
 */

const json = (status, data) => ({
  ok: status < 400,
  status,
  json: () => Promise.resolve(data),
  clone() {
    return json(status, data);
  },
});

const BASE = {
  headline: 'Tool shed',
  description: 'Tools',
  status: 'ACTIVE',
  mode: 'PROPRIETARY',
  visibility: 'PRIVATE',
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  language: 'en',
  owner: 'ABC123',
  is_curator: true,
};
const LIBRARY = { ...BASE, kind: 'LIBRARY' };

function setApi(collection, patchAnswer = json(200, {})) {
  apiFetch.mockImplementation((url, opts = {}) => {
    if (opts.method === 'PATCH') return Promise.resolve(patchAnswer);
    if (url === '/api/v1/theeemes/') return Promise.resolve(json(200, []));
    return Promise.resolve(json(200, collection));
  });
}

async function renderEdit(collection, patchAnswer) {
  setApi(collection, patchAnswer);
  const view = render(
    <MemoryRouter initialEntries={['/collections/COL001/edit']}>
      <Routes>
        <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  await settle(apiFetch);
  await screen.findByDisplayValue(collection.headline);
  return view;
}

const toggle = (container) => container.querySelector('#edit-collection-donations');
const field = (container) => container.querySelector('#edit-collection-donations-info');
const save = () => screen.getByRole('button', { name: 'Save' });
const patchBody = () => {
  const call = apiFetch.mock.calls.find(([, o]) => o?.method === 'PATCH');
  return call && JSON.parse(call[1].body);
};

beforeEach(() => {
  dropHdsStyles();
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
});

describe('where the donations section exists', () => {
  test('a library has it, off, with the text field not drawn', async () => {
    const { container } = await renderEdit(LIBRARY);

    expect(screen.getByRole('heading', { name: en.donations.heading })).toBeInTheDocument();
    expect(toggle(container)).not.toBeNull();
    expect(field(container)).toBeNull();
    expect(save()).toBeEnabled();
  });

  test.each([
    ['stall', { ...BASE, kind: 'STALL', allowed_thing_types: ['GIFT_THING', 'SELL_THING'] }],
    ['shed', { ...BASE, kind: 'SHED', allowed_thing_types: ['RESERVE_THING'] }],
  ])('a %s has none', async (_name, collection) => {
    const { container } = await renderEdit(collection);

    expect(screen.queryByRole('heading', { name: en.donations.heading })).toBeNull();
    expect(toggle(container)).toBeNull();
  });

  test('the creation form of a library has none', async () => {
    apiFetch.mockImplementation(() => Promise.resolve(json(200, [])));
    const { container } = render(
      <MemoryRouter initialEntries={['/library/new']}>
        <Routes>
          <Route path="/:kind/new" element={<CreateCollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await settle(apiFetch);
    await screen.findByRole('heading', { level: 1 });

    expect(container.querySelector('[id$="-donations"]')).toBeNull();
    expect(screen.queryByRole('heading', { name: en.donations.heading })).toBeNull();
  });
});

describe('the switch and the instructions', () => {
  test('turning it on draws a required field, and Save waits for words', async () => {
    const { container } = await renderEdit(LIBRARY);

    fireEvent.click(toggle(container));

    expect(field(container)).not.toBeNull();
    expect(field(container)).toBeRequired();
    expect(screen.getByText(en.donations.infoRequired)).toBeInTheDocument();
    expect(save()).toBeDisabled();

    fireEvent.change(field(container), { target: { value: 'Bring books on Tuesdays' } });
    expect(save()).toBeEnabled();
  });

  test('a map of blank texts is still no words', async () => {
    const { container } = await renderEdit(LIBRARY);
    fireEvent.click(toggle(container));

    fireEvent.change(field(container), { target: { value: '{"es": "", "ca": " "}' } });

    expect(save()).toBeDisabled();
  });

  test('past 2000 characters in one language Save is disabled and the field says why', async () => {
    const { container } = await renderEdit({
      ...LIBRARY,
      accepts_donations: true,
      donations_info: 'ok',
    });

    fireEvent.change(field(container), { target: { value: 'a'.repeat(2001) } });

    expect(screen.getByText(en.donations.maxLength)).toBeInTheDocument();
    expect(save()).toBeDisabled();
  });

  test('the PATCH carries the switch and the trimmed text', async () => {
    const { container } = await renderEdit(LIBRARY);
    fireEvent.click(toggle(container));
    fireEvent.change(field(container), { target: { value: '  ## What we take  ' } });

    fireEvent.click(save());

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toMatchObject({
      accepts_donations: true,
      donations_info: '## What we take',
    });
  });

  test('turning it off hides the field and sends the stored text as it stands', async () => {
    const { container } = await renderEdit({
      ...LIBRARY,
      accepts_donations: true,
      donations_info: 'Bring books',
    });
    expect(field(container)).toHaveValue('Bring books');

    fireEvent.click(toggle(container));

    expect(field(container)).toBeNull();
    expect(save()).toBeEnabled();
    fireEvent.click(save());
    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toMatchObject({ accepts_donations: false, donations_info: 'Bring books' });
  });

  test('a library that is off but has text saves, and turning it on shows that text', async () => {
    const { container } = await renderEdit({ ...LIBRARY, donations_info: 'Written earlier' });

    fireEvent.click(toggle(container));

    expect(field(container)).toHaveValue('Written earlier');
  });

  test("the server's coded refusal is said in the field, not as a toast", async () => {
    const refusal = json(400, {
      code: 'donations_info_required',
      donations_info: ['Write the donation instructions, or turn donations off.'],
    });
    const { container } = await renderEdit(
      { ...LIBRARY, accepts_donations: true, donations_info: 'x' },
      refusal
    );

    fireEvent.click(save());

    expect(await screen.findByText(en.donations.infoRequired)).toBeInTheDocument();
    // HDS points the field at its error line instead of setting aria-invalid.
    expect(field(container).getAttribute('aria-describedby')).toContain('-error');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  test('another 400 still reaches the toast', async () => {
    const { container } = await renderEdit(
      { ...LIBRARY, accepts_donations: true, donations_info: 'x' },
      json(400, { non_field_errors: ['Something else was refused.'] })
    );

    fireEvent.click(save());

    expect(await screen.findByText('Something else was refused.')).toBeInTheDocument();
    expect(field(container).getAttribute('aria-describedby')).not.toContain('-error');
  });
});

describe('accessibility', () => {
  test('the page with donations on has no axe violation', async () => {
    const { container } = await renderEdit({
      ...LIBRARY,
      accepts_donations: true,
      donations_info: 'Bring books',
    });

    expect(await axe(container)).toHaveNoViolations();
  });
});
