import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import en from '../i18n/locales/en.json';

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  ),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import ThingLinkbox from '../components/ThingLinkbox';
import ThingsSection from '../components/collection/ThingsSection';

/**
 * In a COMMUNITY group the card names the member who contributed the thing, and the name
 * links to that member's profile — which opens only for the group's own people. So the
 * link is for someone inside the group (a member, a curator); any other reader, signed
 * in or not, reads the same name as text, and a reader with no session is not told the
 * name at all (the API withholds it).
 */
const THING = {
  code: 'THG001',
  type: 'GIFT_THING',
  owner: 'MEMB02',
  owner_name: 'Lolo',
  headline: 'Chairs',
  description: '',
  status: 'ACTIVE',
  fee: null,
  availability: 'IMMEDIATE',
  location: '',
  condition: '',
  created: '2026-10-01T10:00:00Z',
  tags: [],
  thumbnail_url: '',
  gallery_urls: [],
  transfer_count: 0,
};

const renderCard = ({ thing = THING, ...props } = {}) =>
  render(
    <MemoryRouter>
      <ThingLinkbox
        thing={thing}
        userCode="MEMB01"
        collectionCode="COL001"
        collectionKind="STALL"
        collectionHeadline="Neighbours"
        collectionMode="COMMUNITY"
        onUpdateThing={() => {}}
        {...props}
      />
    </MemoryRouter>
  );

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'MEMB01');
});

describe('the contributing member on a COMMUNITY card', () => {
  test('is a link to their profile for someone inside the group', () => {
    const { container } = renderCard({ insideGroup: true });

    expect(screen.getByRole('link', { name: 'Lolo' })).toHaveAttribute('href', '/MEMB02');
    expect(container.querySelector('.thing-card-owner-link')).not.toBeNull();
  });

  test('is the same name as plain text for a signed-in reader who is not inside', () => {
    const { container } = renderCard();

    expect(container.querySelector('.thing-card-meta')).toHaveTextContent('Lolo');
    expect(screen.queryByRole('link', { name: 'Lolo' })).toBeNull();
    expect(container.querySelector('.thing-card-owner-link')).toBeNull();
  });

  test('is only "A member", as text, for a reader with no session', () => {
    localStorage.clear();
    const { container } = renderCard({
      thing: { ...THING, owner_name: '' },
      userCode: null,
      loginToAct: true,
      insideGroup: false,
    });

    expect(container.querySelector('.thing-card-meta')).toHaveTextContent(en.common.aMember);
    expect(container.querySelector('.thing-card-owner-link')).toBeNull();
  });

  test('a group that is not COMMUNITY has no such line', () => {
    const { container } = renderCard({ collectionMode: 'PROPRIETARY', insideGroup: true });

    expect(container.querySelector('.thing-card-meta')).toBeNull();
  });
});

describe('the collection page hands the cards who is inside', () => {
  const GROUP = {
    code: 'COL001',
    kind: 'STALL',
    mode: 'COMMUNITY',
    status: 'ACTIVE',
    tags: [],
    allowed_thing_types: ['GIFT_THING'],
    things: [THING],
  };
  const renderSection = (collection) =>
    render(
      <MemoryRouter>
        <ThingsSection
          collection={collection}
          code="COL001"
          headline="Neighbours"
          canAddThing={false}
          onUpdateThing={() => {}}
          onJoinedGroup={() => {}}
        />
      </MemoryRouter>
    );

  test.each([
    ['a member', { is_member: true, is_curator: false }, true],
    ['a curator', { is_member: false, is_curator: true }, true],
    ['a reader who is not inside', { is_member: false, is_curator: false }, false],
  ])('%s', (_, fields, linked) => {
    renderSection({ ...GROUP, ...fields });

    expect(screen.queryByRole('link', { name: 'Lolo' }) !== null).toBe(linked);
  });
});
