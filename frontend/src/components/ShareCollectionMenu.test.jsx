import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

// The QR image is a picture a test cannot read, and what this component owns is
// not the drawing — it is *which string* it hands the library. Standing in for
// `qrcode.react` is what turns "a dialog appeared" into "the invite link is the
// thing being encoded"; without it the assertion below passes on an empty code.
vi.mock('qrcode.react', () => ({
  QRCodeSVG: ({ value, title }) => <div data-testid="qr" data-value={value} aria-label={title} />,
}));

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

expect.extend(toHaveNoViolations);

import { apiFetch } from '../services/api';
import ShareCollectionMenu from './ShareCollectionMenu';
import AccountMenu from './AccountMenu';
import en from '../i18n/locales/en.json';

const props = {
  collectionCode: 'COL001',
  collectionHeadline: 'My Collection',
};

function openMenu() {
  fireEvent.click(screen.getByRole('button', { name: /share collection/i }));
}

beforeEach(() => {
  apiFetch.mockClear();
  apiFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ share_url: 'http://x/share/NEWTOKEN', share_token: 'NEWTOKEN' }),
  });
});

describe('ShareCollectionMenu icon trigger', () => {
  test('is one button with an accessible name, and not a combobox', () => {
    // The control is a plain disclosure, like the account and collection menus: a
    // screen reader must hear a button that expands, not a "combo box".
    render(<ShareCollectionMenu {...props} isPublic />);

    expect(screen.queryByRole('combobox')).toBeNull();
    const trigger = screen.getByRole('button', { name: /share collection/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).not.toHaveAttribute('aria-controls');
  });

  test('opens a list of buttons, and says so with aria-expanded and aria-controls', () => {
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();

    const trigger = screen.getByRole('button', { name: /share collection/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    const panel = document.getElementById(trigger.getAttribute('aria-controls'));
    expect(panel).not.toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByRole('listbox')).toBeNull();
    const names = within(panel)
      .getAllByRole('button')
      .map((b) => b.textContent);
    // The order the entries always had.
    expect(names).toEqual([
      'Email',
      'Copy invite link',
      'WhatsApp',
      'QR code',
      'Rotate link',
      'Stop sharing',
    ]);
  });

  test('still opens the full menu from that single trigger', () => {
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();
    for (const name of [/^email$/i, /copy invite link/i, /whatsapp/i, /qr code/i]) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
  });

  test('Escape closes it and returns the focus to the trigger', () => {
    render(<ShareCollectionMenu {...props} isPublic />);
    openMenu();

    fireEvent.keyDown(document, { key: 'Escape' });

    const trigger = screen.getByRole('button', { name: /share collection/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: /whatsapp/i })).toBeNull();
    expect(trigger).toHaveFocus();
  });

  test('a press outside closes it, without taking the focus anywhere', () => {
    render(
      <>
        <button type="button">Outside</button>
        <ShareCollectionMenu {...props} isPublic />
      </>
    );
    openMenu();

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Outside' }));

    expect(screen.queryByRole('button', { name: /whatsapp/i })).toBeNull();
  });

  test('focus moving out of the menu closes it; a blur into nothing does not', () => {
    render(
      <>
        <ShareCollectionMenu {...props} isPublic />
        <button type="button">Outside</button>
      </>
    );
    openMenu();
    const last = screen.getByRole('button', { name: /qr code/i });

    fireEvent.blur(last, { relatedTarget: screen.getByRole('button', { name: /whatsapp/i }) });
    expect(screen.getByRole('button', { name: /whatsapp/i })).toBeInTheDocument();
    fireEvent.blur(last, { relatedTarget: null });
    expect(screen.getByRole('button', { name: /whatsapp/i })).toBeInTheDocument();

    fireEvent.blur(last, { relatedTarget: screen.getByRole('button', { name: 'Outside' }) });
    expect(screen.queryByRole('button', { name: /whatsapp/i })).toBeNull();
  });

  test('choosing an entry closes the panel and the focus is back on the trigger', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn(() => Promise.resolve()) },
    });
    render(<ShareCollectionMenu {...props} isPublic />);
    openMenu();

    fireEvent.click(screen.getByRole('button', { name: /copy invite link/i }));

    const trigger = screen.getByRole('button', { name: /share collection/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveFocus();
    expect(await screen.findByText(/copied to clipboard/i)).toBeInTheDocument();
  });

  test('opening it closes the account menu beside it', () => {
    localStorage.setItem('userCode', 'ABC123');
    render(
      <MemoryRouter>
        <AccountMenu />
        <ShareCollectionMenu {...props} isPublic />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole('button', { name: /your account/i }));
    expect(screen.getByRole('navigation', { name: /your account/i })).toBeInTheDocument();

    // A real press is pointerdown first (what the dismissal listens to), then click.
    const share = screen.getByRole('button', { name: /share collection/i });
    fireEvent.pointerDown(share);
    fireEvent.click(share);

    expect(screen.queryByRole('navigation', { name: /your account/i })).toBeNull();
    expect(share).toHaveAttribute('aria-expanded', 'true');
    localStorage.clear();
  });

  test('has no accessibility violations with the panel open', async () => {
    const { container } = render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('ShareCollectionMenu revoke / rotate', () => {
  test('a PUBLIC collection offers no revoke/rotate (no token to pull back)', () => {
    render(<ShareCollectionMenu {...props} isPublic />);
    openMenu();
    expect(screen.queryByRole('button', { name: /stop sharing/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /rotate link/i })).toBeNull();
  });

  test('without canTakeBack (a dinamizador of a network) the menu shows neither entry', () => {
    render(<ShareCollectionMenu {...props} isPublic={false} />);
    openMenu();
    expect(screen.getByRole('button', { name: /whatsapp/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /stop sharing/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /rotate link/i })).toBeNull();
  });

  test('revoking a PRIVATE share link confirms, then DELETEs the token', async () => {
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: /stop sharing/i }));

    // Consequence confirm appears before any request fires.
    expect(screen.getByText(/the invite link stops working for everyone/i)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /^stop sharing$/i }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/collections/COL001/share-link/',
        expect.objectContaining({ method: 'DELETE' })
      )
    );
  });

  test('rotating a PRIVATE share link POSTs rotate:true', async () => {
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: /rotate link/i }));
    fireEvent.click(screen.getByRole('button', { name: /^rotate link$/i }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/collections/COL001/share-link/',
        expect.objectContaining({ method: 'POST', body: JSON.stringify({ rotate: true }) })
      )
    );
  });

  test('cancelling the confirm fires no request at all', async () => {
    // The confirm is the only thing between a menu pick and an irreversible
    // change to a credential other people are holding. If Cancel still went
    // through, the dialog would be theatre.
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: /stop sharing/i }));

    // The dialog offers Cancel twice — its own close button and the action row —
    // and either one must mean the same thing.
    const cancels = screen.getAllByRole('button', { name: /cancel/i });
    fireEvent.click(cancels[cancels.length - 1]);

    await waitFor(() =>
      expect(screen.queryByText(/the invite link stops working for everyone/i)).toBeNull()
    );
    expect(apiFetch).not.toHaveBeenCalled();
  });
});

/**
 * The two failures that matter here are not crashes — they are the UI saying a
 * credential was withdrawn when it was not.
 *
 * An owner who reads "link rotated" stops worrying about whoever they sent the
 * old link to. If the request actually failed, that old link still works and the
 * person still has access: the owner has been told they closed a door that is
 * standing open. Nothing else in this component is security-relevant in that way,
 * which is why these two get their own tests rather than a shared error case.
 */
describe('a failed revoke or rotate must not claim it worked', () => {
  test('a failed rotate reports the failure, and never says "rotated"', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: /rotate link/i }));
    fireEvent.click(screen.getByRole('button', { name: /^rotate link$/i }));

    expect(await screen.findByText(/couldn't generate the invite link/i)).toBeInTheDocument();
    expect(screen.queryByText(/new link created/i)).toBeNull();
  });

  test('a failed revoke reports the failure, and never says the link is off', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: /stop sharing/i }));
    fireEvent.click(screen.getByRole('button', { name: /^stop sharing$/i }));

    expect(await screen.findByText(/couldn't generate the invite link/i)).toBeInTheDocument();
    expect(screen.queryByText(/sharing stopped/i)).toBeNull();
  });
});

describe('the link is minted once', () => {
  test('a second share action reuses it instead of POSTing again', async () => {
    // For a PRIVATE collection every POST mints a token: asking twice would leave
    // a second credential in the wild.
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn(() => Promise.resolve()) },
    });
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);

    openMenu();
    fireEvent.click(screen.getByRole('button', { name: /copy invite link/i }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1));
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: /copy invite link/i }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(2));

    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(navigator.clipboard.writeText).toHaveBeenLastCalledWith('http://x/share/NEWTOKEN');
  });
});

/**
 * The other half of this menu — the one that actually hands the link over — had
 * no tests at all: `ensureShareUrl` and the four deliveries behind it. The
 * revoke/rotate pair above is guarded because a false success there tells an
 * owner they closed a door that is standing open; these carry two risks of
 * their own. A PUBLIC collection must not be given a bearer token it has no way
 * to take back, and a delivery that silently failed leaves the owner believing
 * a link is on its way to somebody who never got one.
 */
describe('handing the link over', () => {
  let originalLocation;
  let openSpy;

  beforeEach(() => {
    originalLocation = window.location;
    // A plain object, so `mailto:` is recorded instead of navigating jsdom.
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { href: '', origin: 'http://localhost:3000' },
    });
    openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn(() => Promise.resolve()) },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
    vi.restoreAllMocks();
  });

  function pick(name) {
    openMenu();
    fireEvent.click(screen.getByRole('button', { name }));
  }

  test('a PUBLIC group is shared by its own address, and mints no token', async () => {
    // Anyone can read it without an account, so there is nothing to gate — and
    // a share token here would be a credential in the wild that this menu
    // deliberately offers no way to pull back (PUBLIC hides rotate/revoke).
    render(<ShareCollectionMenu {...props} isPublic />);

    pick('Copy invite link');

    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        'http://localhost:3000/collections/COL001'
      )
    );
    expect(apiFetch).not.toHaveBeenCalled();
  });

  test('a PRIVATE group hands out the token the server minted', async () => {
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);

    pick('Copy invite link');

    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://x/share/NEWTOKEN')
    );
    expect(apiFetch).toHaveBeenCalledWith(
      '/api/v1/collections/COL001/share-link/',
      expect.objectContaining({ method: 'POST' })
    );
    expect(await screen.findByText(/copied to clipboard/i)).toBeInTheDocument();
  });

  test('a clipboard that refuses is never reported as a copy', async () => {
    // It refuses for real reasons — no permission, an insecure context, a
    // browser that wants a gesture it didn't see. The owner then pastes
    // whatever was there before into a message to a friend.
    navigator.clipboard.writeText.mockRejectedValue(new Error('denied'));
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);

    pick('Copy invite link');

    expect(await screen.findByText(/couldn't copy the link/i)).toBeInTheDocument();
    expect(screen.queryByText(/copied to clipboard/i)).toBeNull();
  });

  test('a link that cannot be minted shares nothing at all', async () => {
    // Not merely "shows an error": the mail draft must not open with a blank or
    // stale link in it, which is the version the recipient would actually get.
    apiFetch.mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);

    pick('Email');

    expect(await screen.findByText(/couldn't generate the invite link/i)).toBeInTheDocument();
    expect(window.location.href).toBe('');
    expect(openSpy).not.toHaveBeenCalled();
  });

  test('the email draft carries the link and names the collection', async () => {
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);

    pick('Email');

    await waitFor(() => expect(window.location.href).toMatch(/^mailto:\?subject=/));
    const draft = decodeURIComponent(window.location.href);
    expect(draft).toContain('http://x/share/NEWTOKEN');
    expect(draft).toContain('My Collection');
  });

  // The draft opens in the mail client of whoever is sharing — the founder, a
  // co-curator or, in a PUBLIC group, an ordinary member — which already says who
  // is writing. It used to end "Love,\n{{name}}" with the *founder's* name, so a
  // co-curator's email went out signed by somebody else.
  test('the email draft ends at the link: no sign-off and no name', async () => {
    // `ownerName` is a prop this component no longer takes; passing it must not
    // put a name back into the draft.
    render(<ShareCollectionMenu {...props} ownerName="Founder Person" isPublic />);

    pick('Email');

    await waitFor(() => expect(window.location.href).toMatch(/^mailto:\?subject=/));
    const body = decodeURIComponent(window.location.href.split('&body=')[1]);
    expect(body.endsWith('http://localhost:3000/collections/COL001')).toBe(true);
    expect(body).not.toMatch(/Love/);
    expect(body).not.toMatch(/Founder Person/);
  });

  // The person who receives the link may never have heard of OIUEEI; the draft is
  // all they have before deciding to press it. One clause says what it is —
  // neutral on purpose, since a PUBLIC group's link is not a private invitation.
  test('the email draft says what OIUEEI is, and still ends at the link', async () => {
    render(<ShareCollectionMenu {...props} isPublic />);

    pick('Email');

    await waitFor(() => expect(window.location.href).toMatch(/^mailto:\?subject=/));
    const body = decodeURIComponent(window.location.href.split('&body=')[1]);
    expect(body).toContain('on OIUEEI, where a group shares its things among its members.');
    expect(body.endsWith('http://localhost:3000/collections/COL001')).toBe(true);
  });

  test('the WhatsApp text says what OIUEEI is, before the link', async () => {
    render(<ShareCollectionMenu {...props} isPublic />);

    pick('WhatsApp');

    await waitFor(() => expect(openSpy).toHaveBeenCalled());
    const text = decodeURIComponent(openSpy.mock.calls[0][0].split('?text=')[1]);
    expect(text).toMatch(
      /on OIUEEI, where a group shares its things among its members: http:\/\/localhost:3000\/collections\/COL001$/
    );
  });

  test('the WhatsApp text of a library names its kind, and keeps what OIUEEI is', async () => {
    render(<ShareCollectionMenu {...props} collectionKind="LIBRARY" isPublic />);

    pick('WhatsApp');

    await waitFor(() => expect(openSpy).toHaveBeenCalled());
    const text = decodeURIComponent(openSpy.mock.calls[0][0].split('?text=')[1]);
    expect(text).toBe(
      `I'm inviting you to "My Collection", ${en.kinds.LIBRARY.withArticle} on OIUEEI, where a group shares its things among its members: http://localhost:3000/library/COL001`
    );
    expect(en.kinds.LIBRARY.withArticle).toBe('a library of things');
  });

  test('the email draft of a library names its kind, the subject is as it was', async () => {
    render(<ShareCollectionMenu {...props} collectionKind="LIBRARY" isPublic />);

    pick('Email');

    await waitFor(() => expect(window.location.href).toMatch(/^mailto:\?subject=/));
    const [head, rawBody] = window.location.href.split('&body=');
    expect(decodeURIComponent(head)).toBe(
      "mailto:?subject=I'm inviting you to My Collection on OIUEEI"
    );
    const body = decodeURIComponent(rawBody);
    expect(body).toContain(
      `"My Collection", ${en.kinds.LIBRARY.withArticle} on OIUEEI, where a group shares its things among its members.`
    );
    expect(body.endsWith('http://localhost:3000/library/COL001')).toBe(true);
  });

  test('a collection with no kind is shared with the words it always had', async () => {
    render(<ShareCollectionMenu {...props} isPublic />);

    pick('WhatsApp');

    await waitFor(() => expect(openSpy).toHaveBeenCalled());
    const text = decodeURIComponent(openSpy.mock.calls[0][0].split('?text=')[1]);
    expect(text).toContain('"My Collection" on OIUEEI, where');
  });

  test('the WhatsApp hand-off carries the link and cannot reach back', async () => {
    // `noopener` is the load-bearing argument: without it the opened page gets a
    // handle on this one through `window.opener`.
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);

    pick('WhatsApp');

    await waitFor(() => expect(openSpy).toHaveBeenCalled());
    const [url, target, features] = openSpy.mock.calls[0];
    expect(decodeURIComponent(url)).toContain('http://x/share/NEWTOKEN');
    expect(target).toBe('_blank');
    expect(features).toBe('noopener,noreferrer');
  });

  test('the QR encodes the invite link, and prints it underneath', async () => {
    render(<ShareCollectionMenu {...props} isPublic={false} canTakeBack />);

    pick('QR code');

    // What the camera would read …
    expect(await screen.findByTestId('qr')).toHaveAttribute(
      'data-value',
      'http://x/share/NEWTOKEN'
    );
    // … and what the person holding the phone up can check against it.
    expect(screen.getByText('http://x/share/NEWTOKEN')).toBeInTheDocument();
  });
});
