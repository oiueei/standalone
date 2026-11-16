import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { axe, toHaveNoViolations } from 'jest-axe';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import en from '../i18n/locales/en.json';
import { dropHdsStyles } from '../test/dropHdsStyles';

window.scrollTo = vi.fn();
expect.extend(toHaveNoViolations);

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(async () => null),
  getCsrfToken: () => 'tok',
}));

import { apiFetch } from '../services/api';
import DonatePage from './DonatePage';

/**
 * "Donate things": the instructions a library's team wrote for whoever wants to give it
 * things, in the collection's own hero. A page of words: nothing is sent or saved.
 */
const json = (data, status = 200) => ({
  ok: status < 400,
  status,
  json: () => Promise.resolve(data),
});

const COLLECTION = {
  code: 'COL001',
  headline: 'La Marina',
  kind: 'LIBRARY',
  language: '',
  thumbnail_url: 'https://cdn.example/logo.png',
  accepts_donations: true,
  donations_info: '# What we take\n\n- **Books** in good shape\n- Board games',
};

/** Shows where the router ended up, so a redirect is something a test can read. */
function Where() {
  return <output data-testid="where">{useLocation().pathname}</output>;
}

// Mounted under every prefix, as App.jsx does: a stall or a shed asked for at /library/…
// is moved to its own prefix, and there has to be a route there to land on.
function renderPage(data = COLLECTION, status = 200) {
  apiFetch.mockImplementation(() => Promise.resolve(json(data, status)));
  return render(
    <MemoryRouter initialEntries={['/library/COL001/donate']}>
      <Where />
      <Routes>
        {['library', 'stall', 'shed'].map((prefix) => (
          <Route key={prefix} path={`/${prefix}/:code/donate`} element={<DonatePage />} />
        ))}
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  dropHdsStyles();
  vi.clearAllMocks();
  localStorage.clear();
});

describe('DonatePage', () => {
  test('the title is the words of the button, with a way back to the collection', async () => {
    renderPage();

    expect(
      await screen.findByRole('heading', { level: 1, name: en.donations.pageTitle })
    ).toBeVisible();
    expect(en.donations.pageTitle).toBe(en.donations.button);
    expect(screen.getByRole('link', { name: /La Marina/ })).toHaveAttribute(
      'href',
      '/library/COL001'
    );
    expect(document.title).toBe('Donate things to La Marina — OIUEEI');
  });

  test('the instructions are rendered as Markdown', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { level: 2, name: 'What we take' })).toBeVisible();
    expect(screen.getByText('Books').tagName).toBe('STRONG');
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  test('the logo of the collection stands in the hero, as an image with no alt', async () => {
    const { container } = renderPage();
    await screen.findByRole('heading', { level: 1 });

    const logo = container.querySelector('.form-hero img.hero-logo');
    expect(logo).toHaveAttribute('src', 'https://cdn.example/logo.png');
    expect(logo).toHaveAttribute('alt', '');
  });

  test('a reader of another language gets the text written in theirs', async () => {
    renderPage({
      ...COLLECTION,
      donations_info: JSON.stringify({ es: 'Traed libros', en: 'Bring books' }),
    });

    expect(await screen.findByText('Bring books')).toBeVisible();
    expect(screen.queryByText('Traed libros')).toBeNull();
  });

  test.each([
    ['donations are off, with the text still stored', { accepts_donations: false }, 'library'],
    ['it is a stall carrying old data', { kind: 'STALL' }, 'stall'],
    ['it is a shed carrying old data', { kind: 'SHED' }, 'shed'],
  ])('there is no page when %s', async (_why, over, prefix) => {
    renderPage({ ...COLLECTION, ...over });

    // The address first: the redirect to the kind's own prefix has to have happened before the
    // page is judged, or "not found" could be read a moment before the router moves on.
    await waitFor(() =>
      expect(screen.getByTestId('where')).toHaveTextContent(`/${prefix}/COL001/donate`)
    );
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
    expect(screen.queryByText('Board games')).toBeNull();
  });

  test('a 404 is the not-found page', async () => {
    renderPage({}, 404);

    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });

  test('a 403 says the group cannot be read, with a way out', async () => {
    renderPage({}, 403);

    expect(await screen.findByText(en.collectionPage.noPermission)).toBeInTheDocument();
  });

  test('any other failure is said, never an empty page', async () => {
    renderPage({}, 500);

    expect(await screen.findByText(en.collectionPage.errorLoading)).toBeInTheDocument();
  });

  test('a dropped connection is said', async () => {
    apiFetch.mockRejectedValue(new TypeError('Failed to fetch'));
    render(
      <MemoryRouter initialEntries={['/library/COL001/donate']}>
        <Routes>
          <Route path="/library/:code/donate" element={<DonatePage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText(en.common.connectionError)).toBeInTheDocument();
  });

  test('no axe violation', async () => {
    const { container } = renderPage();
    await screen.findByRole('heading', { level: 1 });

    expect(await axe(container)).toHaveNoViolations();
  });
});
