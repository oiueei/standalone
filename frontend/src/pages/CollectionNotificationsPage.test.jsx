import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

const navigate = vi.fn();
vi.mock('react-router', async () => ({
  ...(await vi.importActual('react-router')),
  useNavigate: () => navigate,
}));

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: () => 'tok',
}));

vi.mock('../hooks/useCollectionLanguage', () => ({ default: vi.fn() }));

import { apiFetch } from '../services/api';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import CollectionNotificationsPage from './CollectionNotificationsPage';
import en from '../i18n/locales/en.json';
import { dropHdsStyles } from '../test/dropHdsStyles';
import { press, settle } from '../test/settle';
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

const COLLECTION = {
  code: 'COL001',
  is_curator: true,
  headline: 'Kitchen Collection',
  description: 'Things from the kitchen',
  kind: 'LIBRARY',
  mode: 'COMMUNITY',
  // What other pages own: the PATCH of this page must leave all of it alone.
  allowed_thing_types: ['LEND_THING'],
  tags: ['Kitchen'],
  thumbnail: 'logo.png',
  theeeme: 'T2',
  koro: 'wave',
  home_page: 'https://example.test',
  allow_member_proposals: true,
  welcome_doc: 'welcome.pdf',
  welcome_doc_url: 'https://cdn.test/welcome.pdf',
  digest_frequency: 'WEEKLY',
  language: 'ca',
  email_note: 'We confirm within 48h.',
};

function mockApi({ collection = COLLECTION, save = { ok: true } } = {}) {
  apiFetch.mockImplementation((url, opts) => {
    if (opts?.method === 'PATCH') {
      return Promise.resolve({
        ok: save.ok,
        status: save.status ?? (save.ok ? 200 : 400),
        json: async () => save.body ?? {},
      });
    }
    if (opts?.method === 'POST') {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => collection });
  });
}

const patchBody = () => {
  const call = apiFetch.mock.calls.find(([, opts]) => opts?.method === 'PATCH');
  return call ? JSON.parse(call[1].body) : null;
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/library/COL001/settings/notifications']}>
      <Routes>
        <Route
          path="/library/:code/settings/notifications"
          element={<CollectionNotificationsPage />}
        />
      </Routes>
    </MemoryRouter>
  );

const save = async () => {
  await screen.findByDisplayValue('We confirm within 48h.');
  await settle(apiFetch);
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await settle(apiFetch);
};

beforeEach(() => {
  dropHdsStyles();
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe('CollectionNotificationsPage', () => {
  test('shows what the collection has saved', async () => {
    mockApi();
    renderPage();

    expect(await screen.findByRole('heading', { level: 1, name: 'Notifications' })).toBeVisible();
    expect(await screen.findByDisplayValue('We confirm within 48h.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /view/i })).toHaveAttribute(
      'href',
      'https://cdn.test/welcome.pdf'
    );
    expect(screen.getByRole('combobox', { name: /Digest emails/ })).toHaveTextContent('Weekly');
    expect(
      screen.getByRole('combobox', { name: /Language of the group messages/ })
    ).toHaveTextContent('Català');
  });

  test('explains the languages of the note in a notice above it, with the note’s own help after', async () => {
    mockApi();
    renderPage();

    expect(await screen.findByText(/The email note can hold one text per language/)).toBeVisible();
    expect(
      screen.getByText('{"es": "Estamos en la planta 2", "ca": "Estem a la planta 2"}')
    ).toBeVisible();
    expect(screen.getByText(en.emailNote.helper)).toBeVisible();
  });

  test('saves exactly its own five fields and nothing the collection keeps elsewhere', async () => {
    mockApi();
    renderPage();
    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/library/COL001'));
    const body = patchBody();
    // The page's boundary: a copy of the edit form's body would add `mode`, `koro`,
    // `thumbnail`, `allowed_thing_types`…
    expect(Object.keys(body).sort()).toEqual([
      'allow_member_proposals',
      'digest_frequency',
      'email_note',
      'language',
      'welcome_doc',
    ]);
    expect(body).toEqual({
      allow_member_proposals: true,
      welcome_doc: 'welcome.pdf',
      digest_frequency: 'WEEKLY',
      language: 'ca',
      email_note: 'We confirm within 48h.',
    });
  });

  test('a saved welcome document survives a save that does not touch it', async () => {
    mockApi();
    renderPage();
    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().welcome_doc).toBe('welcome.pdf');
  });

  test('removing the document is what clears it', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('We confirm within 48h.');
    fireEvent.click(screen.getByRole('button', { name: /Remove/ }));

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().welcome_doc).toBe('');
  });

  test('a recommend switch saved as off is still off, and is sent as false', async () => {
    mockApi({ collection: { ...COLLECTION, allow_member_proposals: false } });
    renderPage();
    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().allow_member_proposals).toBe(false);
  });

  test('the summary frequency is the loaded one, with no fallback to NONE', async () => {
    mockApi({ collection: { ...COLLECTION, digest_frequency: 'MONTHLY' } });
    renderPage();
    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().digest_frequency).toBe('MONTHLY');
  });

  test('a collection with no language shows "Automatic", and saving without choosing keeps it blank', async () => {
    mockApi({ collection: { ...COLLECTION, language: '' } });
    renderPage();
    await screen.findByDisplayValue('We confirm within 48h.');
    await settle(apiFetch);
    expect(
      screen.getByRole('combobox', { name: /Language of the group messages/ })
    ).toHaveTextContent('Automatic');
    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().language).toBe('');
    // …while the page itself followed no language but the stored one: none.
    expect(useCollectionLanguage).toHaveBeenLastCalledWith('', [
      'Kitchen Collection',
      'Things from the kitchen',
    ]);
  });

  test('trying another language does not change what the language hook is called with', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('We confirm within 48h.');
    const texts = ['Kitchen Collection', 'Things from the kitchen'];
    await waitFor(() => expect(useCollectionLanguage).toHaveBeenLastCalledWith('ca', texts));

    const combobox = screen.getByRole('combobox', { name: /Language of the group messages/ });
    fireEvent.click(combobox);
    fireEvent.click(await screen.findByRole('option', { name: 'Español' }));

    await waitFor(() => expect(combobox).toHaveTextContent('Español'));
    expect(useCollectionLanguage).toHaveBeenLastCalledWith('ca', texts);
  });

  test('choosing a language on a collection with none records the choice', async () => {
    mockApi({ collection: { ...COLLECTION, language: '' } });
    renderPage();
    await screen.findByDisplayValue('We confirm within 48h.');
    await settle(apiFetch);

    const combobox = screen.getByRole('combobox', { name: /Language of the group messages/ });
    fireEvent.click(combobox);
    fireEvent.click(await screen.findByRole('option', { name: 'Español' }));
    await waitFor(() => expect(combobox).toHaveTextContent('Español'));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().language).toBe('es');
  });

  test('choosing Automatic on a collection with a language takes it back to blank', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('We confirm within 48h.');
    await settle(apiFetch);

    const combobox = screen.getByRole('combobox', { name: /Language of the group messages/ });
    fireEvent.click(combobox);
    fireEvent.click(await screen.findByRole('option', { name: 'Automatic' }));
    await waitFor(() => expect(combobox).toHaveTextContent('Automatic'));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().language).toBe('');
  });

  test('an edited note reaches the PATCH trimmed', async () => {
    mockApi();
    renderPage();
    const note = await screen.findByDisplayValue('We confirm within 48h.');
    await settle(apiFetch);
    fireEvent.change(note, { target: { value: '  We are on floor 2.  ' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().email_note).toBe('We are on floor 2.');
  });

  test('the test email carries the draft on screen, not the saved note', async () => {
    mockApi();
    renderPage();
    const note = await screen.findByDisplayValue('We confirm within 48h.');
    fireEvent.change(note, { target: { value: 'A draft nobody has saved.' } });

    await press(screen.getByRole('button', { name: 'Send me a test email' }));

    expect(await screen.findByText(/Sent to your inbox/)).toBeInTheDocument();
    const post = apiFetch.mock.calls.find(([, o]) => o?.method === 'POST');
    expect(post[0]).toBe('/api/v1/collections/COL001/email-note/test/');
    expect(JSON.parse(post[1].body)).toEqual({ email_note: 'A draft nobody has saved.' });
    expect(patchBody()).toBeNull();
  });

  test('the note’s counter is the 512-per-language one, and past it the error shows at once', async () => {
    mockApi();
    renderPage();
    const note = await screen.findByDisplayValue('We confirm within 48h.');
    await settle(apiFetch);

    fireEvent.change(note, { target: { value: 'Floor 2.' } });
    expect(screen.getByText('8/512')).toBeInTheDocument();

    fireEvent.change(note, { target: { value: 'x'.repeat(513) } });
    expect(screen.getByText('Maximum 512 characters per language.')).toBeInTheDocument();
    expect(note.getAttribute('aria-describedby')).toContain('notifications-email-note-error');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(patchBody()).toBeNull();
  });

  test('Save is disabled while the note is past 512 and enabled again when it fits', async () => {
    mockApi();
    renderPage();
    const note = await screen.findByDisplayValue('We confirm within 48h.');
    await settle(apiFetch);
    const saveButton = screen.getByRole('button', { name: 'Save' });
    expect(saveButton).toBeEnabled();

    fireEvent.change(note, { target: { value: 'x'.repeat(513) } });
    expect(saveButton).toBeDisabled();

    fireEvent.change(note, { target: { value: 'x'.repeat(512) } });
    expect(saveButton).toBeEnabled();
  });

  test('the help line of the summary and of the language reach the control’s accessible name', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('We confirm within 48h.');
    const DIGEST =
      'Automatically email members and whoever runs the group a summary of new things.';
    const LANGUAGE =
      "The language the group's emails are written in. Any member who has set their own language reads them in theirs.";

    expect(screen.getByText(DIGEST)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /Digest emails/ })).toHaveAccessibleName(
      expect.stringContaining(DIGEST)
    );
    expect(screen.getByText(LANGUAGE)).toBeInTheDocument();
    expect(
      screen.getByRole('combobox', { name: /Language of the group messages/ })
    ).toHaveAccessibleName(expect.stringContaining(LANGUAGE));
  });

  test('has no accessibility violations', async () => {
    mockApi();
    const { container } = renderPage();
    await screen.findByDisplayValue('We confirm within 48h.');

    expect(await axe(container)).toHaveNoViolations();
  });

  test('a collection that cannot be read gives no form, so there is nothing to save', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
    );
    renderPage();

    expect(await screen.findByText(en.editCollection.errorLoading)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    expect(patchBody()).toBeNull();
  });

  test('a refusal of the server is shown as its own message', async () => {
    mockApi({
      save: { ok: false, status: 400, body: { email_note: ['Too long, said the server.'] } },
    });
    renderPage();
    await save();

    expect(await screen.findByText(/Too long, said the server/)).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });
});
