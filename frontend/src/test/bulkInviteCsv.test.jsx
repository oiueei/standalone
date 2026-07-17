import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({ apiFetch: vi.fn() }));

import { apiFetch } from '../services/api';
import BulkInviteCsv from '../components/BulkInviteCsv';

const fileInput = (container) => container.querySelector('input[type="file"]');
const pick = (container, file) => fireEvent.change(fileInput(container), { target: { files: [file] } });

const csvFile = (text) => new File([text], 'guests.csv', { type: 'text/csv' });

function jsonResponse(data, ok = true, status = ok ? 200 : 400) {
  return { ok, status, json: () => Promise.resolve(data) };
}

const renderBulkInvite = (onInvited = vi.fn()) => ({
  onInvited,
  ...render(<BulkInviteCsv collectionCode="COL001" onInvited={onInvited} />),
});

beforeEach(() => {
  vi.clearAllMocks();
  apiFetch.mockResolvedValue(jsonResponse({ invited: 0, skipped: [] }));
});

describe('BulkInviteCsv', () => {
  test('previews the addresses and sends them', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ invited: 2, skipped: [] }));
    const { container, onInvited } = renderBulkInvite();

    pick(container, csvFile('email,name\nlala@mail.com,\nlele@mail.com,LeLe'));

    expect(await screen.findByText('Preview (2)')).toBeInTheDocument();
    expect(screen.getByText('lala@mail.com')).toBeInTheDocument();
    expect(screen.getByText('lele@mail.com — LeLe')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Send 2 invitations'));

    await waitFor(() => expect(onInvited).toHaveBeenCalled());
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/COL001/invite/bulk/', {
      method: 'POST',
      body: JSON.stringify({
        invites: [{ email: 'lala@mail.com' }, { email: 'lele@mail.com', name: 'LeLe' }],
      }),
    });
    // The preview clears once sent, so the list can't be sent twice by accident.
    expect(screen.queryByText('Preview (2)')).toBeNull();
  });

  // The endpoint is best-effort, not atomic: some addresses get in, the rest come
  // back with a reason, and the owner needs to see both halves.
  test('reports the invited count and every skipped address with its reason', async () => {
    apiFetch.mockResolvedValue(
      jsonResponse({
        invited: 1,
        skipped: [
          { email: 'nope', reason: 'invalid' },
          { email: 'lala@mail.com', reason: 'already_member' },
          { email: 'lele@mail.com', reason: 'already_invited' },
          { email: 'lili@mail.com', reason: 'duplicate' },
        ],
      })
    );
    const { container } = renderBulkInvite();

    pick(container, csvFile('email\nlolo@mail.com'));
    fireEvent.click(await screen.findByText('Send 1 invitations'));

    expect(await screen.findByText(/1 invitations sent\./)).toBeInTheDocument();
    expect(screen.getByText('4 skipped:')).toBeInTheDocument();
    expect(screen.getByText('nope — invalid email')).toBeInTheDocument();
    expect(screen.getByText('lala@mail.com — already a member')).toBeInTheDocument();
    expect(screen.getByText('lele@mail.com — already invited')).toBeInTheDocument();
    expect(screen.getByText('lili@mail.com — duplicate')).toBeInTheDocument();
  });

  test('an unknown skip reason falls back to "invalid email" rather than a blank', async () => {
    apiFetch.mockResolvedValue(
      jsonResponse({ invited: 0, skipped: [{ email: 'nope@mail.com', reason: 'something_new' }] })
    );
    const { container } = renderBulkInvite();

    pick(container, csvFile('email\nlolo@mail.com'));
    fireEvent.click(await screen.findByText('Send 1 invitations'));

    expect(await screen.findByText('nope@mail.com — invalid email')).toBeInTheDocument();
  });

  test('refuses more than 100 rows', async () => {
    const { container } = renderBulkInvite();
    const rows = Array.from({ length: 101 }, (_, i) => `guest${i}@mail.com`).join('\n');

    pick(container, csvFile(`email\n${rows}`));

    expect(await screen.findByText('You can invite up to 100 people at once.')).toBeInTheDocument();
    expect(screen.queryByText(/^Preview/)).toBeNull();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  test('refuses a row with no email', async () => {
    const { container } = renderBulkInvite();

    pick(container, csvFile('email,name\nlala@mail.com,Lala\n,Lele'));

    expect(await screen.findByText('Every row needs an email.')).toBeInTheDocument();
    expect(screen.queryByText(/^Preview/)).toBeNull();
  });

  test('refuses an empty file', async () => {
    const { container } = renderBulkInvite();

    pick(container, csvFile('email\n'));

    expect(await screen.findByText('No rows found in that file.')).toBeInTheDocument();
  });

  test('surfaces the error detail from a 400', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ error: 'This collection is inactive.' }, false));
    const { container, onInvited } = renderBulkInvite();

    pick(container, csvFile('email\nlala@mail.com'));
    fireEvent.click(await screen.findByText('Send 1 invitations'));

    expect(await screen.findByText('This collection is inactive.')).toBeInTheDocument();
    expect(onInvited).not.toHaveBeenCalled();
  });

  test('surfaces a rate limit', async () => {
    apiFetch.mockResolvedValue(jsonResponse({}, false, 429));
    const { container } = renderBulkInvite();

    pick(container, csvFile('email\nlala@mail.com'));
    fireEvent.click(await screen.findByText('Send 1 invitations'));

    expect(
      await screen.findByText('Too many attempts — please wait a moment and try again.')
    ).toBeInTheDocument();
  });

  test('surfaces a dropped connection', async () => {
    apiFetch.mockRejectedValue(new Error('network down'));
    const { container } = renderBulkInvite();

    pick(container, csvFile('email\nlala@mail.com'));
    fireEvent.click(await screen.findByText('Send 1 invitations'));

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
  });
});
