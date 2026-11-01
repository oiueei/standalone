import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import BulkInviteResult from './BulkInviteResult';

/**
 * The summary of a batch of invitations, shared by the CSV tool and by the invitations
 * field of `/invites` when it holds several addresses.
 * `test/bulkInviteCsv.test.jsx` and `pages/ManageInvitesPage.test.jsx` pin it through
 * their own flows; these pin the component by itself.
 */
describe('BulkInviteResult', () => {
  test('with no result it is an empty live region, there already for what comes', () => {
    const { container } = render(<BulkInviteResult result={null} />);

    const region = container.querySelector('[role="status"]');
    expect(region).not.toBeNull();
    expect(region).toBeEmptyDOMElement();
  });

  test('says how many were invited, and nothing about skipped when none were', () => {
    render(<BulkInviteResult result={{ invited: 3, skipped: [] }} />);

    expect(screen.getByText('3 invitations sent.')).toBeInTheDocument();
    expect(screen.queryByText(/skipped/)).toBeNull();
    expect(screen.queryByRole('list')).toBeNull();
  });

  test('lists each skipped address with its reason in words', () => {
    render(
      <BulkInviteResult
        result={{
          invited: 1,
          skipped: [
            { email: 'bad', reason: 'invalid' },
            { email: 'lala@your-domain.test', reason: 'duplicate' },
            { email: 'lele@your-domain.test', reason: 'already_member' },
            { email: 'lili@your-domain.test', reason: 'already_invited' },
            { email: 'lolo@your-domain.test', reason: 'daily_limit' },
            { email: 'lulu@your-domain.test', reason: 'already_asked' },
          ],
        }}
      />
    );

    expect(screen.getByText('6 skipped:')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'bad — invalid email',
      'lala@your-domain.test — duplicate',
      'lele@your-domain.test — already a member',
      'lili@your-domain.test — already invited',
      'lolo@your-domain.test — daily invitation limit reached',
      'lulu@your-domain.test — already had an invitation',
    ]);
  });

  test('a reason it does not know reads as an invalid address', () => {
    render(
      <BulkInviteResult
        result={{ invited: 0, skipped: [{ email: 'lulu@your-domain.test', reason: '??' }] }}
      />
    );

    expect(screen.getByText('lulu@your-domain.test — invalid email')).toBeInTheDocument();
  });

  test('nobody invited is a plain (info) notice, somebody invited a success one', () => {
    // HDS gives the default type no class of its own and a success one `--success`.
    const { container, rerender } = render(
      <BulkInviteResult result={{ invited: 0, skipped: [] }} />
    );
    const notice = () => container.querySelector('section');

    expect(notice().className).not.toMatch(/success|error|alert/);
    rerender(<BulkInviteResult result={{ invited: 2, skipped: [] }} />);
    expect(notice().className).toMatch(/success/);
  });
});
