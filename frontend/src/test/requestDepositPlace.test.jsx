import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import RequestThingPage from '../pages/RequestThingPage';

/**
 * Where the deposit stands on the request page: after the fields that choose the
 * dates, right above the notice about who sees the requester's name and the button
 * that sends — what is read last before asking. The price stays at the top.
 */
const POLICY = 'Back when it comes home in one piece';

const LEND_THING = {
  code: 'LEND01',
  type: 'LEND_THING',
  headline: 'Ladder',
  fee: 3,
  deposit: 50,
  deposit_policy: POLICY,
  collection_code: 'COL001',
  available_today: true,
  next_available: null,
};

function mockResponse(data) {
  return { ok: true, status: 200, json: () => Promise.resolve(data) };
}

function renderPage(thing) {
  apiFetch.mockImplementation((url) => {
    if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
    if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
    return Promise.resolve(mockResponse({}));
  });
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: `/collections/COL001/things/${thing.code}/request`, state: {} }]}
    >
      <Routes>
        <Route path="/collections/:code/things/:thingCode/request" element={<RequestThingPage />} />
      </Routes>
    </MemoryRouter>
  );
}

const follows = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
});

describe('RequestThingPage — where the deposit stands', () => {
  test('the deposit and its policy come after the last field and before the notice and the button', async () => {
    const { container } = renderPage(LEND_THING);
    await screen.findByText(/Request: Ladder/);

    const deposit = screen.getByText('Deposit.').closest('p');
    const policy = screen.getByTestId('deposit-policy');
    const lastField = container.querySelector('#request-end-date');
    const notice = screen.getByText('Whoever runs this thing will see your name and email.');
    const send = screen.getByRole('button', { name: 'Borrow' });

    expect(follows(lastField, deposit)).toBe(true);
    expect(follows(deposit, policy)).toBe(true);
    expect(follows(policy, notice)).toBe(true);
    expect(follows(notice, send)).toBe(true);
  });

  test('the price stays at the top, before the dates', async () => {
    const { container } = renderPage(LEND_THING);
    await screen.findByText(/Request: Ladder/);

    const price = screen.getByText('Price:').closest('p');
    expect(follows(price, container.querySelector('#request-start-date'))).toBe(true);
  });

  test('a thing with no deposit has no deposit line and no policy', async () => {
    renderPage({ ...LEND_THING, deposit: null });
    await screen.findByText(/Request: Ladder/);

    expect(screen.queryByText('Deposit.')).toBeNull();
    expect(screen.queryByTestId('deposit-policy')).toBeNull();
  });

  test('a deposit with no policy has the line alone', async () => {
    renderPage({ ...LEND_THING, deposit_policy: '' });
    await screen.findByText(/Request: Ladder/);

    expect(screen.getByText('Deposit.')).toBeInTheDocument();
    expect(screen.queryByTestId('deposit-policy')).toBeNull();
  });
});
