import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { dropHdsStyles } from '../test/dropHdsStyles';
import { MemoryRouter, Routes, Route } from 'react-router';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import en from '../i18n/locales/en.json';

window.scrollTo = vi.fn();
expect.extend(toHaveNoViolations);

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(async (res) => (await res.json()).error || null),
  getCsrfToken: () => 'tok',
}));

vi.mock('../utils/uploadImage', async (importOriginal) => ({
  ...(await importOriginal()),
  uploadImage: vi.fn(),
}));

import { apiFetch } from '../services/api';
import { uploadImage } from '../utils/uploadImage';
import OrganisationPage from './OrganisationPage';

/**
 * A curator sets up the page they have in a group: name, logo, About and contact, in any
 * collection; in a **network** also the pickup point and the conditions of their loans.
 * The page reads and writes only their own (`/collections/:code/point/`), sends only the
 * identity fields outside a network, and says what the server says when it is not theirs
 * to have (403 for a plain member).
 */
const json = (data, status = 200) => ({
  ok: status < 400,
  status,
  json: () => Promise.resolve(data),
});

const COLLECTION = {
  code: 'COL001',
  headline: 'Neighbourhood network',
  language: '',
  mode: 'NETWORK',
  kind: 'LIBRARY',
};

const EMPTY_POINT = {
  entity_name: '',
  address: '',
  hours_note: '',
  contact: '',
  logo: '',
  logo_url: null,
  about: '',
  weekdays: [],
  closed_dates: [],
  deposit_policy: '',
  request_info: '',
  email_note: '',
};

function mockApi({
  point = json(EMPTY_POINT),
  put = json(EMPTY_POINT),
  collection = COLLECTION,
} = {}) {
  apiFetch.mockImplementation((url, options) => {
    if (url.endsWith('/point/')) return Promise.resolve(options?.method === 'PUT' ? put : point);
    return Promise.resolve(json(collection));
  });
}

const NOT_A_NETWORK = { ...COLLECTION, mode: 'PROPRIETARY' };

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/library/COL001/organisation']}>
      <Routes>
        <Route path="/library/:code/organisation" element={<OrganisationPage />} />
        <Route path="/library/:code" element={<div>THE COLLECTION</div>} />
      </Routes>
    </MemoryRouter>
  );

const putCall = () => apiFetch.mock.calls.find(([, o]) => o?.method === 'PUT');

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
  mockApi();
});

describe('OrganisationPage — a field past its limit', () => {
  const saveButton = () => screen.getByRole('button', { name: 'Save' });
  const FIELDS = [
    { label: /^About/, limit: 2000, message: en.organisation.aboutMaxLength },
    { label: /Deposit policy/i, limit: 256, message: en.rental.depositPolicyMaxLength },
    { label: en.requestInfo.label, limit: 512, message: en.requestInfo.maxLength },
    { label: en.emailNote.label, limit: 512, message: en.emailNote.maxLength },
  ];

  test.each(FIELDS)(
    'in a network, $limit characters is the most the field takes, and Save waits',
    async ({ label, limit, message }) => {
      renderPage();
      const field = await screen.findByRole('textbox', { name: label });
      expect(saveButton()).toBeEnabled();

      fireEvent.change(field, { target: { value: 'x'.repeat(limit + 1) } });
      expect(screen.getByText(message)).toBeInTheDocument();
      expect(saveButton()).toBeDisabled();

      fireEvent.change(field, { target: { value: 'x'.repeat(limit) } });
      expect(screen.queryByText(message)).toBeNull();
      expect(saveButton()).toBeEnabled();
    }
  );

  test('outside a network only About holds Save back', async () => {
    mockApi({
      point: json({ ...EMPTY_POINT, request_info: 'x'.repeat(600) }),
      collection: NOT_A_NETWORK,
    });
    renderPage();
    // The long note is stored but its field is not on the page.
    const about = await screen.findByRole('textbox', { name: /^About/ });
    expect(screen.queryByRole('textbox', { name: en.requestInfo.label })).toBeNull();
    expect(saveButton()).toBeEnabled();

    fireEvent.change(about, { target: { value: 'x'.repeat(2001) } });
    expect(saveButton()).toBeDisabled();
  });
});

describe('OrganisationPage — in a network', () => {
  test('shows the fields of the point the dinamizador already has', async () => {
    mockApi({
      point: json({
        ...EMPTY_POINT,
        entity_name: 'Cooperativa La Fusteria',
        address: 'Carrer Major 4',
        hours_note: 'martes y jueves de 18 a 20',
        contact: '93 000 00 00',
        weekdays: [1, 3],
        closed_dates: ['2030-08-15'],
        request_info: 'Bring the card',
      }),
    });
    renderPage();

    expect(await screen.findByLabelText(/Name of the organisation/)).toHaveValue(
      'Cooperativa La Fusteria'
    );
    expect(screen.getByLabelText('Address')).toHaveValue('Carrer Major 4');
    expect(screen.getByLabelText(/Pickup and return hours/)).toHaveValue(
      'martes y jueves de 18 a 20'
    );
    expect(screen.getByLabelText(/Contact \(web or phone\)/)).toHaveValue('93 000 00 00');
    expect(screen.getByRole('button', { name: 'Tuesday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Monday' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByLabelText(/Holidays and closures/)).toHaveValue('15/08/2030');
  });

  test('says how the group sees them, and what the pickup point is for', async () => {
    renderPage();

    expect(await screen.findByText(en.organisation.noticeTitle)).toBeInTheDocument();
    expect(screen.getByText(en.organisation.notice)).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 1, name: en.organisation.pageTitle })
    ).toBeVisible();
    expect(
      screen.getByRole('heading', { level: 2, name: en.organisation.pickupTitle })
    ).toBeVisible();
    expect(screen.getByText(en.organisation.pickupIntro)).toBeInTheDocument();
    expect(screen.getByText('Pickup and return days')).toBeInTheDocument();
    expect(screen.queryByText(/Days you lend and take back/)).toBeNull();
  });

  test('saves exactly what was written, to the dinamizador’s own point', async () => {
    renderPage();
    fireEvent.change(await screen.findByLabelText(/Name of the organisation/), {
      target: { value: '  Sindicat de Llogateres ' },
    });
    fireEvent.change(screen.getByLabelText('Address'), { target: { value: 'Plaça 1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Wednesday' }));

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(putCall()).toBeTruthy());
    const [url, options] = putCall();
    expect(url).toBe('/api/v1/collections/COL001/point/');
    expect(JSON.parse(options.body)).toEqual({
      entity_name: 'Sindicat de Llogateres',
      logo: '',
      about: '',
      contact: '',
      address: 'Plaça 1',
      hours_note: '',
      weekdays: [2],
      closed_dates: '',
      deposit_policy: '',
      request_info: '',
      email_note: '',
    });
    // Saving ends the visit: the reader is back on the collection, with no notice left behind.
    expect(await screen.findByText('THE COLLECTION')).toBeInTheDocument();
    expect(screen.queryByText('Saved.')).toBeNull();
  });

  test('says what the server refused when saving', async () => {
    mockApi({ put: json({ error: 'That is not a date' }, 400) });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Save' }));

    expect(await screen.findByText('That is not a date')).toBeInTheDocument();
    expect(screen.queryByText('THE COLLECTION')).toBeNull();
  });

  test.each([
    ['a 500', () => mockApi({ point: json({}, 500) }), en.organisation.errorLoading],
    [
      'a network failure',
      () =>
        apiFetch.mockImplementation((url) =>
          url.endsWith('/point/')
            ? Promise.reject(new Error('offline'))
            : Promise.resolve(json(COLLECTION))
        ),
      en.common.connectionError,
    ],
  ])(
    'when loading the point fails with %s, the page says so and offers no form',
    async (_, arrange, message) => {
      arrange();
      renderPage();

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    }
  );

  describe('when saving fails', () => {
    const SAVE_FAILURES = [
      [
        'a 400 with a message says that message',
        () => json({ error: 'That is not a date' }, 400),
        'That is not a date',
      ],
      [
        'a 400 without a readable message says the generic one',
        () => json({}, 400),
        en.organisation.errorSaving,
      ],
      ['a 429 says to wait', () => json({}, 429), en.common.tooManyAttempts],
      ['a 500 says the generic one', () => json({}, 500), en.organisation.errorSaving],
      [
        'a network failure says so',
        () => Promise.reject(new Error('offline')),
        en.common.connectionError,
      ],
    ];

    test.each(SAVE_FAILURES)(
      '%s, stays on the page and lets the curator try again',
      async (_, put, message) => {
        mockApi();
        apiFetch.mockImplementation((url, options) => {
          if (!url.endsWith('/point/')) return Promise.resolve(json(COLLECTION));
          return options?.method === 'PUT'
            ? Promise.resolve().then(put)
            : Promise.resolve(json(EMPTY_POINT));
        });
        renderPage();
        fireEvent.click(await screen.findByRole('button', { name: 'Save' }));

        expect(await screen.findByText(message)).toBeInTheDocument();
        expect(screen.queryByText('THE COLLECTION')).toBeNull();
        expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
      }
    );
  });

  test('a plain member is told the page is the team’s', async () => {
    mockApi({ point: json({}, 403) });
    renderPage();

    expect(await screen.findByText(en.organisation.notACurator)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
  });

  test('asks for the logo, after the name, in the collections’ folder', async () => {
    const { container } = renderPage();
    await screen.findByLabelText(/Name of the organisation/);

    expect(screen.getByText(en.organisation.logoLabel)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(en.organisation.logoHelper))).toBeInTheDocument();
    const name = screen.getByLabelText(/Name of the organisation/);
    const upload = container.querySelector('input[type="file"]');
    expect(name.compareDocumentPosition(upload) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    fireEvent.change(upload, {
      target: { files: [new File(['x'], 'logo.png', { type: 'image/png' })] },
    });
    await waitFor(() =>
      expect(uploadImage).toHaveBeenCalledWith(expect.any(File), 'oiueei/collections')
    );
  });

  test('a logo that was uploaded goes in the PUT', async () => {
    uploadImage.mockResolvedValue({
      publicId: 'oiueei/collections/fusteria',
      url: 'https://cdn/x',
    });
    const { container } = renderPage();
    await screen.findByLabelText(/Name of the organisation/);
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [new File(['x'], 'logo.png', { type: 'image/png' })] },
    });
    await screen.findByRole('button', { name: /Remove/ });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(putCall()).toBeTruthy());
    expect(JSON.parse(putCall()[1].body).logo).toBe('oiueei/collections/fusteria');
  });

  test('a saved logo shows, and taking it off sends an empty one', async () => {
    mockApi({
      point: json({
        ...EMPTY_POINT,
        logo: 'oiueei/collections/fusteria',
        logo_url: 'https://cdn/oiueei/collections/fusteria',
      }),
    });
    renderPage();
    await screen.findByLabelText(/Name of the organisation/);

    fireEvent.click(await screen.findByRole('button', { name: /Remove/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(putCall()).toBeTruthy());
    expect(JSON.parse(putCall()[1].body).logo).toBe('');
  });

  test('saving without touching the logo sends the one it has', async () => {
    mockApi({
      point: json({
        ...EMPTY_POINT,
        logo: 'oiueei/collections/fusteria',
        logo_url: 'https://cdn/oiueei/collections/fusteria',
      }),
    });
    renderPage();
    await screen.findByLabelText(/Name of the organisation/);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(putCall()).toBeTruthy());
    expect(JSON.parse(putCall()[1].body).logo).toBe('oiueei/collections/fusteria');
  });

  test('the logo’s help says what it is for and which images the upload takes', async () => {
    const { container } = renderPage();
    await screen.findByLabelText(/Name of the organisation/);

    const help = `${en.organisation.logoHelper} ${en.collectionSettings.logoHelper}`;
    expect(container.querySelector('.image-upload')).toHaveTextContent(help);
  });
});

describe('OrganisationPage — outside a network', () => {
  beforeEach(() => mockApi({ collection: NOT_A_NETWORK }));

  test('asks for name, logo, About and contact, in that order, and nothing of a pickup point', async () => {
    const { container } = renderPage();
    const name = await screen.findByLabelText(/Name of the organisation/);
    const about = screen.getByLabelText(en.organisation.aboutLabel);
    const contact = screen.getByLabelText(/Contact \(web or phone\)/);
    const logo = container.querySelector('input[type="file"]');

    const follows = (a, b) => a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
    expect(follows(name, logo)).toBeTruthy();
    expect(follows(logo, about)).toBeTruthy();
    expect(follows(about, contact)).toBeTruthy();
    expect(screen.queryByRole('heading', { name: en.organisation.pickupTitle })).toBeNull();
    expect(screen.queryByRole('heading', { name: en.networkPoint.conditionsTitle })).toBeNull();
    expect(screen.queryByLabelText('Address')).toBeNull();
    expect(screen.queryByLabelText(en.requestInfo.label)).toBeNull();
    expect(screen.queryByLabelText(en.rental.depositPolicyLabel)).toBeNull();
    expect(screen.queryByLabelText(en.emailNote.label)).toBeNull();
    expect(screen.queryByRole('button', { name: 'Tuesday' })).toBeNull();
  });

  test('the PUT carries exactly the four identity fields', async () => {
    mockApi({
      collection: NOT_A_NETWORK,
      point: json({ ...EMPTY_POINT, entity_name: 'Taller', about: 'Hola **mundo**' }),
    });
    renderPage();
    fireEvent.change(await screen.findByLabelText(/Contact \(web or phone\)/), {
      target: { value: ' taller.example ' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(putCall()).toBeTruthy());
    expect(JSON.parse(putCall()[1].body)).toEqual({
      entity_name: 'Taller',
      logo: '',
      about: 'Hola **mundo**',
      contact: 'taller.example',
    });
  });

  test('the About keeps the 2000-per-language count and blocks the save past it', async () => {
    renderPage();
    const about = await screen.findByLabelText(en.organisation.aboutLabel);

    fireEvent.change(about, { target: { value: 'Hola' } });
    expect(screen.getByText('4/2000')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();

    fireEvent.change(about, { target: { value: 'x'.repeat(2001) } });
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  test('a saved About shows', async () => {
    mockApi({ collection: NOT_A_NETWORK, point: json({ ...EMPTY_POINT, about: 'Somos vecinas' }) });
    renderPage();

    expect(await screen.findByLabelText(en.organisation.aboutLabel)).toHaveValue('Somos vecinas');
  });
});

describe('OrganisationPage — accessibility', () => {
  test.each([
    ['a network', COLLECTION],
    ['a collection that is not a network', NOT_A_NETWORK],
  ])('%s: no violations, with every notice open', async (_, collection) => {
    mockApi({ collection });
    const { container } = renderPage();
    await screen.findByLabelText(/Name of the organisation/);
    dropHdsStyles();

    expect(await axe(container)).toHaveNoViolations();
  });
});
