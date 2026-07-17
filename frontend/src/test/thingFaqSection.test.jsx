import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
}));

import { apiFetch, extractApiError } from '../services/api';
import ThingFaqSection from '../components/ThingFaqSection';

function jsonResponse(data, ok = true, status = ok ? 200 : 400) {
  return { ok, status, json: () => Promise.resolve(data) };
}

// React writes a textarea's value into its text content, so a plain text query
// matches the box the text was typed into as readily as the question or answer
// that came back — and would pass even if neither ever rendered. Every assertion
// about published copy uses this.
const RENDERED = { ignore: 'script, style, textarea' };

const faq = (overrides = {}) => ({
  code: 'FAQ001',
  question: 'Does it fit a 60cm oven?',
  questioner_name: 'Lele',
  answer: null,
  is_visible: true,
  ...overrides,
});

// The mount fetch is the fallback; each test overrides the routes it cares about.
function setApi({ faqs = [], next = null, routes = {} } = {}) {
  apiFetch.mockImplementation((url, options) => {
    for (const [pattern, response] of Object.entries(routes)) {
      if (url.includes(pattern)) return Promise.resolve(response(url, options));
    }
    return Promise.resolve(jsonResponse({ results: faqs, next }));
  });
}

function renderFaq(props = {}) {
  const onToast = vi.fn();
  return {
    onToast,
    ...render(
      <ThingFaqSection
        thingCode="THG001"
        isOwner={false}
        isAuthenticated
        btnStyle={{}}
        btnSecondaryStyle={{}}
        tc={{ color_03: 'copper' }}
        onToast={onToast}
        {...props}
      />
    ),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  extractApiError.mockResolvedValue('');
  setApi();
});

// ════════════════════════════════════════════════════════════════════════
// Asking — logged-in non-owners only
// ════════════════════════════════════════════════════════════════════════
describe('ThingFaqSection — asking a question', () => {
  test('a member asks, and the question joins the list', async () => {
    setApi({
      routes: {
        '/faq/': (url, options) =>
          options?.method === 'POST'
            ? jsonResponse(faq({ question: 'Does it fit a 60cm oven?' }))
            : jsonResponse({ results: [], next: null }),
      },
    });
    const { onToast } = renderFaq();

    expect(await screen.findByText('No questions yet.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Question'), {
      target: { value: 'Does it fit a 60cm oven?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }));

    expect(await screen.findByText('Does it fit a 60cm oven?', RENDERED)).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/things/THG001/faq/', {
      method: 'POST',
      body: JSON.stringify({ question: 'Does it fit a 60cm oven?' }),
    });
    expect(onToast).toHaveBeenCalledWith({ type: 'success', message: 'Question sent.' });
    // The box empties, so the same question can't be sent twice by reflex.
    expect(screen.getByLabelText('Question')).toHaveValue('');
  });

  test('the send button stays disabled until something is typed', () => {
    renderFaq();

    const send = screen.getByRole('button', { name: 'Send question' });
    expect(send).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Question'), { target: { value: '   ' } });
    expect(send).toBeDisabled(); // whitespace is not a question

    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Real question?' } });
    expect(send).toBeEnabled();
  });

  test('the owner is not offered the ask form', async () => {
    setApi({ faqs: [faq()] });
    renderFaq({ isOwner: true });

    expect(await screen.findByText('Does it fit a 60cm oven?')).toBeInTheDocument();
    expect(screen.queryByLabelText('Question')).toBeNull();
  });

  test('an anonymous visitor is not offered the ask form', async () => {
    setApi({ faqs: [faq()] });
    renderFaq({ isAuthenticated: false });

    expect(await screen.findByText('Does it fit a 60cm oven?')).toBeInTheDocument();
    expect(screen.queryByLabelText('Question')).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// Answering + hiding — owner only
// ════════════════════════════════════════════════════════════════════════
describe('ThingFaqSection — the owner replies', () => {
  test('an answer replaces the reply box and shows under the question', async () => {
    setApi({
      faqs: [faq()],
      routes: {
        '/faq/FAQ001/answer/': () => jsonResponse(faq({ answer: 'Yes, it is 58cm wide.' })),
      },
    });
    const { onToast } = renderFaq({ isOwner: true });

    fireEvent.change(await screen.findByLabelText('Reply'), {
      target: { value: 'Yes, it is 58cm wide.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Reply' }));

    // Answered: there is nothing left to reply to, and the answer takes its place.
    // (Matched loosely — HDS's Highlight prefixes the reference with its own dash.)
    await waitFor(() => expect(screen.queryByLabelText('Reply')).toBeNull());
    expect(screen.getByText(/Yes, it is 58cm wide\./, RENDERED)).toBeInTheDocument();

    expect(apiFetch).toHaveBeenCalledWith('/api/v1/faq/FAQ001/answer/', {
      method: 'POST',
      body: JSON.stringify({ answer: 'Yes, it is 58cm wide.' }),
    });
    expect(onToast).toHaveBeenCalledWith({ type: 'success', message: 'Answer sent.' });
  });

  test('a member gets neither the reply box nor the hide control', async () => {
    setApi({ faqs: [faq()] });
    renderFaq();

    expect(await screen.findByText('Does it fit a 60cm oven?')).toBeInTheDocument();
    expect(screen.queryByLabelText('Reply')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Hide' })).toBeNull();
  });

  test('hiding dims the question and marks it, and showing puts it back', async () => {
    setApi({
      faqs: [faq({ answer: 'Yes, it is 58cm wide.' })],
      routes: { '/hide/': () => jsonResponse({}), '/show/': () => jsonResponse({}) },
    });
    const { container } = renderFaq({ isOwner: true });
    const card = () => container.querySelector('.faq-grid > div');

    fireEvent.click(await screen.findByRole('button', { name: 'Hide' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/faq/FAQ001/hide/', { method: 'POST' })
    );
    // Hidden from guests, but still there for the owner — dimmed and labelled.
    expect(await screen.findByText('(Hidden)')).toBeInTheDocument();
    expect(card()).toHaveStyle({ opacity: '0.6' });
    expect(screen.getByText('Does it fit a 60cm oven?')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Show' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/faq/FAQ001/show/', { method: 'POST' })
    );
    await waitFor(() => expect(card()).toHaveStyle({ opacity: '1' }));
    expect(screen.queryByText('(Hidden)')).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// The pager
// ════════════════════════════════════════════════════════════════════════
describe('ThingFaqSection — Load more', () => {
  test('appends the next page and then retires the button', async () => {
    setApi({
      faqs: [faq({ code: 'FAQ001', question: 'First page question' })],
      next: 'https://www.oiueei.com/api/v1/things/THG001/faq/?page=2',
      routes: {
        '?page=2': () =>
          jsonResponse({
            results: [faq({ code: 'FAQ002', question: 'Second page question' })],
            next: null,
          }),
      },
    });
    renderFaq();

    fireEvent.click(await screen.findByRole('button', { name: 'Load more' }));

    expect(await screen.findByText('Second page question')).toBeInTheDocument();
    expect(screen.getByText('First page question')).toBeInTheDocument();
    // The API hands back an absolute URL; it is made relative so the request
    // goes through the same origin/proxy as every other call.
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/things/THG001/faq/?page=2');
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull());
  });

  test('a single page offers no pager', async () => {
    setApi({ faqs: [faq()], next: null });
    renderFaq();

    expect(await screen.findByText('Does it fit a 60cm oven?')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// Failure — everything reports through onToast
// ════════════════════════════════════════════════════════════════════════
describe('ThingFaqSection — failures', () => {
  async function ask() {
    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'A question?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  }

  test('a rejected question surfaces the server detail', async () => {
    extractApiError.mockResolvedValue('That question is too long.');
    setApi({
      routes: {
        '/faq/': (url, options) =>
          options?.method === 'POST' ? jsonResponse({}, false) : jsonResponse({ results: [] }),
      },
    });
    const { onToast } = renderFaq();

    await ask();

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({ type: 'error', message: 'That question is too long.' })
    );
  });

  test('a rejected question with no usable body falls back to our own copy', async () => {
    extractApiError.mockResolvedValue(null);
    setApi({
      routes: {
        '/faq/': (url, options) =>
          options?.method === 'POST' ? jsonResponse({}, false) : jsonResponse({ results: [] }),
      },
    });
    const { onToast } = renderFaq();

    await ask();

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({ type: 'error', message: 'Error sending question.' })
    );
  });

  test('a rate-limited question says so rather than showing an empty 429 body', async () => {
    setApi({
      routes: {
        '/faq/': (url, options) =>
          options?.method === 'POST'
            ? jsonResponse({}, false, 429)
            : jsonResponse({ results: [] }),
      },
    });
    const { onToast } = renderFaq();

    await ask();

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({
        type: 'error',
        message: 'Too many attempts — please wait a moment and try again.',
      })
    );
  });

  test('a dropped connection while asking is reported', async () => {
    setApi({
      routes: {
        '/faq/': (url, options) => {
          if (options?.method === 'POST') throw new Error('network down');
          return jsonResponse({ results: [] });
        },
      },
    });
    const { onToast } = renderFaq();

    await ask();

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({ type: 'error', message: 'Connection error.' })
    );
  });

  test('a rejected answer surfaces our copy', async () => {
    extractApiError.mockResolvedValue(null);
    setApi({ faqs: [faq()], routes: { '/answer/': () => jsonResponse({}, false) } });
    const { onToast } = renderFaq({ isOwner: true });

    fireEvent.change(await screen.findByLabelText('Reply'), { target: { value: 'Yes.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reply' }));

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({ type: 'error', message: 'Error sending answer.' })
    );
  });

  test('a failed hide leaves the question shown and says which way it failed', async () => {
    setApi({ faqs: [faq({ answer: 'Yes.' })], routes: { '/hide/': () => jsonResponse({}, false) } });
    const { onToast, container } = renderFaq({ isOwner: true });

    fireEvent.click(await screen.findByRole('button', { name: 'Hide' }));

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({
        type: 'error',
        message: 'Error hiding the question.',
      })
    );
    expect(container.querySelector('.faq-grid > div')).toHaveStyle({ opacity: '1' });
  });

  test('a failed show is reported the other way round', async () => {
    setApi({
      faqs: [faq({ answer: 'Yes.', is_visible: false })],
      routes: { '/show/': () => jsonResponse({}, false) },
    });
    const { onToast } = renderFaq({ isOwner: true });

    fireEvent.click(await screen.findByRole('button', { name: 'Show' }));

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({
        type: 'error',
        message: 'Error showing the question.',
      })
    );
  });
});

// A list endpoint that isn't paginated hands back a bare array.
describe('ThingFaqSection — response shapes', () => {
  test('an unpaginated array response still lists the questions', async () => {
    apiFetch.mockResolvedValue(jsonResponse([faq({ question: 'Bare array question' })]));
    renderFaq();

    expect(await screen.findByText('Bare array question')).toBeInTheDocument();
  });

  test('a failed initial fetch leaves the empty state rather than breaking the page', async () => {
    apiFetch.mockRejectedValue(new Error('network down'));
    renderFaq();

    expect(await screen.findByText('No questions yet.')).toBeInTheDocument();
  });
});
