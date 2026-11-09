import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, test, expect, beforeEach, vi } from 'vitest';
vi.mock('../services/api', () => ({ apiFetch: vi.fn() }));

import { apiFetch } from '../services/api';
import { press, settle } from '../test/settle';
import PageLayout from './PageLayout';
import { declarations, declarationsInMedia } from '../test/cssRules';

/**
 * `heroActions`: buttons in the hero, after the title and the
 * description, in a `.button-row-wide` of their own. Only a thing's page uses it
 * for now, and its test says which buttons; this one is the slot itself and the
 * stylesheet that makes it behave, since jsdom applies no CSS.
 */
const renderLayout = (props) =>
  render(
    <MemoryRouter>
      <PageLayout title="A title" description="A description" {...props}>
        <p>content</p>
      </PageLayout>
    </MemoryRouter>
  );

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('PageLayout — heroActions', () => {
  test('are painted in the hero after the title and the description, in a wide row', () => {
    const { container } = renderLayout({
      heroActions: (
        <>
          <button type="button">First</button>
          <button type="button">Second</button>
        </>
      ),
    });

    const row = container.querySelector('.form-hero-content .hero-actions');
    expect(row).toHaveClass('button-row-wide');
    expect([...row.children].map((c) => c.textContent)).toEqual(['First', 'Second']);
    const title = screen.getByRole('heading', { name: 'A title' });
    const description = screen.getByText('A description');
    // Document order: title, description, then the buttons.
    expect(title.compareDocumentPosition(description)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(description.compareDocumentPosition(row)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    // …and not in the content below the hero.
    expect(container.querySelector('.page-container .hero-actions')).toBeNull();
  });

  test('without any, there is no row at all', () => {
    const { container } = renderLayout({});

    expect(container.querySelector('.hero-actions')).toBeNull();
    expect(container.querySelector('.form-hero .button-row-wide')).toBeNull();
  });

  test('the same for null — what a page passes when it has nothing to decide', () => {
    const { container } = renderLayout({ heroActions: null });

    expect(container.querySelector('.hero-actions')).toBeNull();
  });
});

/**
 * `collectionMenu`: the collection's menu in the corner of a
 * page that reads a collection — a thing's — after the account menu. When it is
 * there, "Requests to me" is its first entry and the account menu stops offering it.
 */
describe('PageLayout — collectionMenu', () => {
  const MENU = <span data-testid="the-collection-menu">menu</span>;
  const meSays = (receives) =>
    apiFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ receives_requests: receives }),
    });

  test('it sits in the corner after the account menu', () => {
    localStorage.setItem('userCode', 'ABC123');
    const { container } = renderLayout({ collectionMenu: MENU });

    const corners = container.querySelector('.hero-corners');
    expect([...corners.children].map((c) => c.className || c.dataset.testid)).toEqual([
      'account-menu',
      'the-collection-menu',
    ]);
  });

  test('without it the corner is the account menu alone', () => {
    localStorage.setItem('userCode', 'ABC123');
    const { container } = renderLayout({});

    expect(container.querySelector('.hero-corners').children).toHaveLength(1);
  });

  test('with it, the account menu does not offer "Requests to me"', async () => {
    localStorage.setItem('userCode', 'ABC123');
    meSays(true);
    renderLayout({ collectionMenu: MENU });

    await press(screen.getByRole('button', { name: /your account/i }));

    expect(screen.getByRole('link', { name: 'My requests' })).toBeInTheDocument();
    await settle(apiFetch);
    expect(screen.queryByRole('link', { name: 'Requests to me' })).not.toBeInTheDocument();
  });

  test('without it, the account menu keeps the link', async () => {
    localStorage.setItem('userCode', 'ABC123');
    meSays(true);
    renderLayout({});

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Requests to me' })).toBeInTheDocument()
    );
  });
});

/**
 * `offerSignIn`: whether a reader with no session gets the corner's
 * "Sign in" icon. `MagicLinkJoinPage` passes its own through, so a door that leaves out
 * "already have an account?" leaves out the icon too. Nothing changes with a session.
 */
describe('PageLayout — offerSignIn', () => {
  test('by default a reader with no session has the "Sign in" icon in the corner', () => {
    const { container } = renderLayout({});

    expect(container.querySelector('.hero-corners a[href="/login"]')).not.toBeNull();
  });

  test('with offerSignIn={false} the corner is empty for a reader with no session', () => {
    const { container } = renderLayout({ offerSignIn: false });

    expect(container.querySelector('.hero-corners')).toBeEmptyDOMElement();
    expect(screen.queryByRole('link', { name: 'Sign in' })).toBeNull();
  });

  test('with a session the account menu is there whatever it says', () => {
    localStorage.setItem('userCode', 'ABC123');
    renderLayout({ offerSignIn: false });

    expect(screen.getByRole('button', { name: /your account/i })).toBeInTheDocument();
  });
});

describe('PageLayout — heroClassName', () => {
  test('is added to the hero next to form-hero', () => {
    const { container } = renderLayout({ heroClassName: 'form-hero--request' });

    expect(container.querySelector('.form-hero')).toHaveClass('form-hero', 'form-hero--request');
  });

  test('without one the hero is the plain form-hero, with no stray class', () => {
    const { container } = renderLayout({});

    expect(container.querySelector('.form-hero').className).toBe('form-hero');
  });
});

describe('the request hero title stylesheet', () => {
  const REQUEST_TITLE = '.form-hero--request .form-hero-title';

  test('is the thing page title: same size, weight, line height and tracking', () => {
    for (const property of ['font-size', 'font-weight', 'line-height', 'letter-spacing']) {
      expect(declarations(REQUEST_TITLE, property)).toEqual(declarations('.page-title', property));
    }
  });

  test('wins over the larger title of 768px and up: no media query sets it, and it has the higher specificity', () => {
    // Nothing in a media query touches this selector, so it can only lose to a rule with
    // more specificity than two classes; the desktop rule has one.
    expect(declarationsInMedia('(min-width: 768px)', REQUEST_TITLE, 'font-size')).toEqual([]);
    expect(declarationsInMedia('(min-width: 768px)', '.form-hero-title', 'font-size')).toEqual([
      'var(--fontsize-heading-xl)',
    ]);
    expect(REQUEST_TITLE.split('.').length - 1).toBeGreaterThan(
      '.form-hero-title'.split('.').length - 1
    );
  });

  test('does not touch the hero colour', () => {
    expect(declarations(REQUEST_TITLE, 'color')).toEqual([]);
  });
});

describe('the hero actions stylesheet', () => {
  const DESKTOP = '(min-width: 768px)';

  test('the row wraps and keeps its buttons at the top, so a panel can take a line of its own', () => {
    expect(declarations('.hero-actions', 'flex-wrap')).toEqual(['wrap']);
    expect(declarations('.hero-actions', 'align-items')).toEqual(['flex-start']);
  });

  test('an opened InlineConfirm goes last, under the buttons, the whole width of the row from 768px', () => {
    const panel = '.hero-actions > .thing-report-confirm';
    expect(declarations(panel, 'order')).toEqual(['1']);
    // A flex-basis of the whole line means something in a row only; in the column
    // of a phone `align-self` is what gives it the width.
    expect(declarations(panel, 'align-self')).toEqual(['stretch']);
    expect(declarations(panel, 'flex')).toEqual(declarationsInMedia(DESKTOP, panel, 'flex'));
    expect(declarationsInMedia(DESKTOP, panel, 'flex')).toEqual(['1 1 100%']);
  });

  test('the confirm panel has its own text colour, not the hero text colour', () => {
    // A light surface wherever it opens: on a dark theeeme, text taken from the
    // hero would be white on near-white.
    const colours = declarations('.thing-report-confirm', 'color');
    expect(colours).toEqual(['var(--color-black-90)']);
    expect(colours.join(' ')).not.toMatch(/hero-text-color/);
  });
});

describe('PageLayout — logoUrl', () => {
  test('the logo is an image with no alt between the way back and the title', () => {
    const { container } = renderLayout({
      backTo: '/library/COL001',
      backLabel: 'La Marina',
      logoUrl: 'https://cdn.example/logo.png',
      heroClassName: 'form-hero--collection',
    });

    const logo = container.querySelector('.form-hero-content img.hero-logo');
    expect(logo).toHaveAttribute('src', 'https://cdn.example/logo.png');
    expect(logo).toHaveAttribute('alt', '');
    const back = container.querySelector('.back-link');
    const title = screen.getByRole('heading', { name: 'A title' });
    expect(back.compareDocumentPosition(logo)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(logo.compareDocumentPosition(title)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  test.each([undefined, ''])('without a logo (%j) the hero paints no image', (logoUrl) => {
    const { container } = renderLayout({ logoUrl });

    expect(container.querySelector('.form-hero img')).toBeNull();
  });
});
