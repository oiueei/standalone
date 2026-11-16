import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ receives_requests: true }),
    })
  ),
}));
vi.mock('../deployment', async (orig) => ({
  ...(await orig()),
  curatorGuidePath: '/guide',
}));

import CollectionMenu from './CollectionMenu';
import { iconOf } from '../test/menuEntryIcon';
import { settle } from '../test/settle';

const download = { downloading: false, download: vi.fn() };
const downloads = { calendar: download, stats: download, collectionExport: download };
const digest = (muted) => ({ muted, busy: false, toggle: vi.fn() });

const renderMenu = (props) =>
  render(
    <MemoryRouter>
      <CollectionMenu
        code="COL001"
        kind="LIBRARY"
        headline="Tools"
        welcomeDocUrl="https://example.test/welcome.pdf"
        {...props}
      />
    </MemoryRouter>
  );

const openMenu = async () => {
  fireEvent.click(screen.getByRole('button', { name: 'Collection options' }));
  await settle();
};

beforeEach(() => localStorage.setItem('userCode', 'ABC123'));

describe('CollectionMenu — an icon before every entry', () => {
  test('a curator’s entries each open with their own decorative icon and keep their name', async () => {
    renderMenu({ hasDateThings: true, downloads, digest: digest(false) });
    await openMenu();

    const entries = [
      ['link', 'Requests to me', 'requests-to-me'],
      ['link', "The group's welcome document (PDF)", 'document'],
      ['link', 'Add thing', 'plus'],
      ['link', 'Add several at once (CSV)', 'upload'],
      ['link', 'Manage members', 'group'],
      ['link', 'My organisation', 'company'],
      ['link', 'Invite many at once (CSV)', 'invite-many'],
      ['button', 'Download the calendar (ICS)', 'calendar-event'],
      ['button', 'Download the stats (CSV)', 'graph-columns'],
      ['button', 'Download the whole collection (JSON)', 'download'],
      ['link', 'If you run a group', 'question-circle'],
      ['button', 'Mute the summaries', 'bell-crossed'],
    ];
    for (const [role, text, icon] of entries) {
      const entry = screen.getAllByRole(role).find((e) => e.textContent.includes(text));
      expect(entry, text).toBeTruthy();
      expect(iconOf(entry, text)).toBe(icon);
    }
  });

  test('a muted group offers the summaries again with the bell', async () => {
    renderMenu({ downloads, digest: digest(true) });
    await openMenu();

    const entry = screen.getByRole('button', { name: 'Get the summaries again' });
    expect(iconOf(entry, 'Get the summaries again')).toBe('bell');
  });

  test('a member’s exit wears the sign-out door and their summaries the crossed bell', async () => {
    renderMenu({ isCurator: false, digest: digest(false) });
    await openMenu();

    const leave = screen.getByRole('link', { name: 'Leave the group' });
    expect(iconOf(leave, 'Leave the group')).toBe('signout');
    const mute = screen.getByRole('button', { name: 'Mute the summaries' });
    expect(iconOf(mute, 'Mute the summaries')).toBe('bell-crossed');
  });
});
