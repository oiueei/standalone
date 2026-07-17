import { render, screen, waitFor } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

expect.extend(toHaveNoViolations);

// The busier hero (headline + tags + owner buttons + share menu) is what S8
// adds a photo composition to on top of — HeroPhoto itself is unit-tested
// separately (HeroPhoto.test.jsx); this checks the combination doesn't
// introduce an axe violation the way the shared smoke.test.jsx fixture
// (thumbnail_url: '') never exercises.
const COLLECTION_WITH_PHOTO = {
  code: 'COL001',
  headline: 'Kitchen Collection',
  description: 'Things from the kitchen',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  mode: 'PROPRIETARY',
  owner: 'ABC123',
  owner_name: 'Test User',
  thumbnail_url: 'https://res.cloudinary.com/demo/image/upload/oiueei/collections/cover.jpg',
  tags: [],
  things: [],
  invites: [],
  is_paused: false,
  is_swap: false,
  is_share: false,
  allowed_thing_types: [],
};

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(COLLECTION_WITH_PHOTO) })
  ),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import CollectionPage from './CollectionPage';

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
});

describe('CollectionPage with a collection thumbnail', () => {
  test('renders the photo hero with no accessibility violations', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(container.querySelector('.hero-photo-wrap')).toBeTruthy();
    });
    expect(container.querySelector('.form-hero--photo')).toBeTruthy();
    expect(container.querySelector('img.hero-photo')).toHaveAttribute(
      'src',
      COLLECTION_WITH_PHOTO.thumbnail_url
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('CollectionPage anonymous visitor intro', () => {
  test('shows a join link for a signed-out visitor', async () => {
    localStorage.clear();
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    const link = await screen.findByRole('link', { name: /join to take part/i });
    expect(link).toHaveAttribute('href', '/collections/COL001/join');
  });

  test('does not show the join link for an authenticated visitor', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(container.querySelector('.form-hero-title')).toHaveTextContent('Kitchen Collection');
    });
    expect(screen.queryByRole('link', { name: /join to take part/i })).toBeNull();
  });
});
