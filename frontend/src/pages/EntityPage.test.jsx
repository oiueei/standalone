import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
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
import EntityPage from './EntityPage';

/**
 * The page a curator has in a group, as anyone who can read the group sees it: the
 * entity's logo and name in the collection's hero, its contact and About and, in a
 * network, where and when to collect and return and a way to what it lends. Read from
 * the collection's own answer (`points`), with no request of its own.
 */
const json = (data, status = 200) => ({
  ok: status < 400,
  status,
  json: () => Promise.resolve(data),
});

const POINT = {
  code: 'PNT001',
  user: 'TEAM01',
  display_name: 'Cooperativa Brúixola',
  entity_name: 'Cooperativa Brúixola',
  address: 'Carrer del Rellotge 7',
  hours_note: 'Tuesdays and Thursdays, 6 to 8 pm',
  contact: 'brixola.example · 600 000 000',
  logo: 'oiueei/collections/x',
  logo_url: 'https://cdn.example/brixola.png',
  about: 'We are a **small** cooperative.',
  weekdays: [1, 3],
  closed_dates: [],
};

const COLLECTION = {
  code: 'COL001',
  headline: 'La Marina',
  kind: 'LIBRARY',
  mode: 'NETWORK',
  language: '',
  owner: 'OWNER1',
  owner_name: 'Lala',
  co_owners: [{ code: 'TEAM01', name: 'Lulu' }],
  points: [POINT],
};

function mockCollection(data = COLLECTION, status = 200) {
  apiFetch.mockImplementation(() => Promise.resolve(json(data, status)));
}

const renderPage = (userCode = 'TEAM01', path = '/library/COL001/organisation/') =>
  render(
    <MemoryRouter initialEntries={[`${path}${userCode}`]}>
      <Routes>
        <Route path="/library/:code/organisation/:userCode" element={<EntityPage />} />
      </Routes>
    </MemoryRouter>
  );

const heading = () => screen.findByRole('heading', { level: 1 });

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  mockCollection();
});

describe('EntityPage — in a network', () => {
  test('shows the logo, the name and whose pickup point it is, in the hero', async () => {
    const { container } = renderPage();

    expect(await heading()).toHaveTextContent('Cooperativa Brúixola');
    const logo = container.querySelector('img.hero-logo');
    expect(logo).toHaveAttribute('src', POINT.logo_url);
    expect(logo).toHaveAttribute('alt', '');
    expect(screen.getByText('Pickup point of La Marina')).toBeInTheDocument();
    expect(screen.queryByText(/^Runs /)).toBeNull();
  });

  test('has the way back to the group, and no buttons in the hero', async () => {
    const { container } = renderPage();
    await heading();

    expect(screen.getByRole('link', { name: /La Marina/ })).toHaveAttribute(
      'href',
      '/library/COL001'
    );
    expect(container.querySelector('.form-hero .button-row-wide')).toBeNull();
    expect(
      container.querySelector('.form-hero a.hds-button, .form-hero button.hds-button')
    ).toBeNull();
  });

  test('lists contact, address, hours and days, each with its icon, and the About', async () => {
    const { container } = renderPage();
    await heading();

    const rows = [...container.querySelectorAll('.thing-card-info-row')].map(
      (row) => row.textContent
    );
    expect(rows).toEqual([
      'Contact: brixola.example · 600 000 000',
      'Address: Carrer del Rellotge 7',
      'Pickup and return hours: Tuesdays and Thursdays, 6 to 8 pm',
      'Pickup and return days: Tuesday and Thursday',
    ]);
    expect(container.querySelectorAll('.thing-card-info-row svg[aria-hidden="true"]')).toHaveLength(
      4
    );
    expect(screen.getByRole('heading', { level: 2, name: 'About' })).toBeVisible();
    expect(screen.getByText('small').tagName).toBe('STRONG');
  });

  test('offers what they lend: the network filtered by them', async () => {
    renderPage();
    await heading();

    expect(screen.getByRole('link', { name: 'See what they lend' })).toHaveAttribute(
      'href',
      '/library/COL001/TEAM01'
    );
  });

  test('a row with nothing in it is not painted', async () => {
    mockCollection({
      ...COLLECTION,
      points: [{ ...POINT, address: '', hours_note: '', weekdays: [], contact: '' }],
    });
    const { container } = renderPage();
    await heading();

    expect(container.querySelector('.thing-card-info')).toBeNull();
  });

  test('without an About there is no About heading', async () => {
    mockCollection({ ...COLLECTION, points: [{ ...POINT, about: '' }] });
    renderPage();
    await heading();

    expect(screen.queryByRole('heading', { level: 2, name: 'About' })).toBeNull();
  });

  test('the About reads in the reader’s language', async () => {
    mockCollection({
      ...COLLECTION,
      points: [{ ...POINT, about: '{"es": "Hola", "en": "Hello there"}' }],
    });
    renderPage();
    await heading();

    expect(screen.getByText('Hello there')).toBeVisible();
    expect(screen.queryByText('Hola')).toBeNull();
  });

  test('the founder has a page too, and the founder’s name stands in for no entity', async () => {
    mockCollection({ ...COLLECTION, points: [] });
    renderPage('OWNER1');

    expect(await heading()).toHaveTextContent('Lala');
    expect(screen.getByText('Pickup point of La Marina')).toBeInTheDocument();
  });
});

describe('EntityPage — outside a network', () => {
  const OUTSIDE = {
    ...COLLECTION,
    mode: 'PROPRIETARY',
    // What the columns hold is not served outside a network; even if it were, it is not shown.
    points: [{ ...POINT, address: 'Somewhere', hours_note: 'Always', weekdays: [2] }],
  };

  beforeEach(() => mockCollection(OUTSIDE));

  test('says whom they run it for, and shows only the contact and the About', async () => {
    const { container } = renderPage();

    expect(await heading()).toHaveTextContent('Cooperativa Brúixola');
    expect(screen.getByText('Runs La Marina')).toBeInTheDocument();
    expect(
      [...container.querySelectorAll('.thing-card-info-row')].map((r) => r.textContent)
    ).toEqual(['Contact: brixola.example · 600 000 000']);
    expect(screen.getByRole('heading', { level: 2, name: 'About' })).toBeVisible();
    expect(screen.queryByText(/Somewhere|Always|Wednesday/)).toBeNull();
  });

  test('has no button to what they lend', async () => {
    renderPage();
    await heading();

    expect(screen.queryByRole('link', { name: 'See what they lend' })).toBeNull();
  });
});

describe('EntityPage — who has a page', () => {
  test('a curator who never set one is shown by their account name, with no logo and no About', async () => {
    mockCollection({ ...COLLECTION, points: [] });
    const { container } = renderPage();

    expect(await heading()).toHaveTextContent('Lulu');
    expect(container.querySelector('img.hero-logo')).toBeNull();
    expect(screen.queryByRole('heading', { level: 2, name: 'About' })).toBeNull();
  });

  test.each(['MEMBER1', 'NOBODY'])(
    '%s is not the team of the group: the page is not found',
    async (userCode) => {
      renderPage(userCode);

      expect(await screen.findByText(en.notFound.title)).toBeInTheDocument();
      expect(screen.queryByText('Pickup point of La Marina')).toBeNull();
    }
  );

  test('a reader with no session sees it (the group is public)', async () => {
    localStorage.removeItem('userCode');
    renderPage();

    expect(await heading()).toHaveTextContent('Cooperativa Brúixola');
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/COL001/', expect.anything());
  });

  test('a group the reader cannot read says so, with a way out', async () => {
    mockCollection({}, 403);
    renderPage();

    expect(await screen.findByText(en.collectionPage.noPermission)).toBeInTheDocument();
  });

  test('a group that does not exist is the page not found', async () => {
    mockCollection({}, 404);
    renderPage();

    expect(await screen.findByText(en.notFound.title)).toBeInTheDocument();
  });

  test('the page of the founder shows no About heading when the founder has no page', async () => {
    mockCollection({ ...COLLECTION, points: [] });
    renderPage('OWNER1');
    await heading();

    expect(within(document.body).queryByRole('heading', { level: 2 })).toBeNull();
  });
});

describe('EntityPage — accessibility', () => {
  test.each([
    ['a network', COLLECTION],
    ['a group that is not a network', { ...COLLECTION, mode: 'PROPRIETARY' }],
  ])('%s: no violations', async (_, collection) => {
    mockCollection(collection);
    const { container } = renderPage();
    await heading();
    dropHdsStyles();

    expect(await axe(container)).toHaveNoViolations();
  });
});
