import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import en from '../i18n/locales/en.json';

window.scrollTo = vi.fn();

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
import NetworkPointPage from './NetworkPointPage';

/**
 * A network's dinamizador sets up the pickup point of the entity they answer for:
 * where and when members collect and return, their own days and closures, and the
 * conditions of their own loans. The page reads and writes only their own point
 * (`/collections/:code/point/`), and says what the server says when it is not theirs
 * to have (404 outside a network, 403 for a plain member).
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
  weekdays: [],
  closed_dates: [],
  deposit_policy: '',
  request_info: '',
  email_note: '',
};

function mockApi({ point = json(EMPTY_POINT), put = json(EMPTY_POINT) } = {}) {
  apiFetch.mockImplementation((url, options) => {
    if (url.endsWith('/point/')) return Promise.resolve(options?.method === 'PUT' ? put : point);
    return Promise.resolve(json(COLLECTION));
  });
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/library/COL001/point']}>
      <Routes>
        <Route path="/library/:code/point" element={<NetworkPointPage />} />
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

describe('NetworkPointPage', () => {
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

    expect(await screen.findByLabelText(/Name of the entity/)).toHaveValue(
      'Cooperativa La Fusteria'
    );
    expect(screen.getByLabelText('Address')).toHaveValue('Carrer Major 4');
    expect(screen.getByLabelText(/Pickup and return hours/)).toHaveValue(
      'martes y jueves de 18 a 20'
    );
    expect(screen.getByLabelText(/Contact of the entity/)).toHaveValue('93 000 00 00');
    expect(screen.getByRole('button', { name: 'Tuesday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Monday' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByLabelText(/Holidays and closures/)).toHaveValue('15/08/2030');
  });

  test('speaks to the one dinamizador and says the days are for pickup and return alike', async () => {
    renderPage();

    expect(
      await screen.findByText(
        'You lend your things from your pickup point: the entity you answer for, where they are collected and returned, and when. Everyone who sees the network sees it.'
      )
    ).toBeInTheDocument();
    expect(screen.getByText('Pickup and return days')).toBeInTheDocument();
    expect(screen.queryByText(/Days you lend and take back/)).toBeNull();
  });

  test('saves exactly what was written, to the dinamizador’s own point', async () => {
    renderPage();
    fireEvent.change(await screen.findByLabelText(/Name of the entity/), {
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
      address: 'Plaça 1',
      hours_note: '',
      contact: '',
      logo: '',
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

  test('a collection that is not a network has no pickup points', async () => {
    mockApi({ point: json({}, 404) });
    renderPage();

    expect(await screen.findByText('Only a network has pickup points.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
  });

  test('a plain member is told the point is the team’s', async () => {
    mockApi({ point: json({}, 403) });
    renderPage();

    expect(
      await screen.findByText('Only the team of the network has a pickup point.')
    ).toBeInTheDocument();
  });

  test('asks for the entity’s logo, after its name, in the collections’ folder', async () => {
    const { container } = renderPage();
    await screen.findByLabelText(/Name of the entity/);

    expect(screen.getByText('Entity logo')).toBeInTheDocument();
    expect(screen.getByText(/Shown beside the name on everything you lend\./)).toBeInTheDocument();
    const name = screen.getByLabelText(/Name of the entity/);
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
    await screen.findByLabelText(/Name of the entity/);
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
    await screen.findByLabelText(/Name of the entity/);

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
    await screen.findByLabelText(/Name of the entity/);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(putCall()).toBeTruthy());
    expect(JSON.parse(putCall()[1].body).logo).toBe('oiueei/collections/fusteria');
  });

  test('the logo’s help says what it is for and which images the upload takes', async () => {
    const { container } = renderPage();
    await screen.findByLabelText(/Name of the entity/);

    const help = `${en.networkPoint.logoHelper} ${en.collectionSettings.logoHelper}`;
    expect(container.querySelector('.image-upload')).toHaveTextContent(help);
  });
});
