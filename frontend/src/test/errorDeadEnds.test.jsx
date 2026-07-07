import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// PageLayout/RouteFocusReset call scrollTo in jsdom.
window.scrollTo = vi.fn();

// Every fetch fails, so each page lands in its error branch (DESIGN A1).
vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) })
  ),
  extractApiError: vi.fn(() => Promise.resolve('Not found')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import CollectionPage from '../pages/CollectionPage';
import ThingPage from '../pages/ThingPage';

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'U1');
  localStorage.setItem(
    'theeemeColors',
    JSON.stringify({
      color_01: 'bus',
      color_02: 'fog',
      color_03: 'summer',
      color_04: 'black',
      color_05: 'black',
      color_06: 'white',
    })
  );
  localStorage.setItem('koro', 'basic');
});

describe('error screens are not navigation dead ends (DESIGN A1)', () => {
  test('CollectionPage error state offers a way home', async () => {
    render(
      <MemoryRouter initialEntries={['/collections/COL404']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    expect(await screen.findByRole('link', { name: /home/i })).toHaveAttribute('href', '/');
  });

  test('ThingPage error state offers a way home', async () => {
    render(
      <MemoryRouter initialEntries={['/things/THG404']}>
        <Routes>
          <Route path="/things/:thingCode" element={<ThingPage />} />
        </Routes>
      </MemoryRouter>
    );
    expect(await screen.findByRole('link', { name: /home/i })).toHaveAttribute('href', '/');
  });
});
