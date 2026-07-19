import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, test, expect, vi, afterEach } from 'vitest';
import RespondWishPage from './RespondWishPage';

function renderPage(kindSlug) {
  return render(
    <MemoryRouter initialEntries={[`/things/WSH001/respond/${kindSlug}`]}>
      <Routes>
        <Route path="/things/:thingCode/respond/:kind" element={<RespondWishPage />} />
        <Route path="/" element={<div>HOME</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const submit = () => fireEvent.click(screen.getByRole('button', { name: 'Send answer' }));

describe('RespondWishPage (answering a wish)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('"I know where" sends kind, message and the optional link', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ code: 'WRSP01', kind: 'KNOW_WHERE' }),
    });
    renderPage('know-where');

    fireEvent.change(screen.getByLabelText(/Message/), {
      target: { value: 'Try the shop on 5th' },
    });
    fireEvent.change(screen.getByLabelText(/Link \(optional\)/), {
      target: { value: 'https://shop.example.com' },
    });
    submit();

    await screen.findByText('Answer sent.');
    const [url, options] = globalThis.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/things/WSH001/responses/');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({
      kind: 'KNOW_WHERE',
      message: 'Try the shop on 5th',
      url: 'https://shop.example.com',
    });
  });

  test('"I can make it" sends kind, message and the offer', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ code: 'WRSP02', kind: 'CAN_MAKE' }),
    });
    renderPage('can-make');

    fireEvent.change(screen.getByLabelText(/Message/), {
      target: { value: 'I can knit you one' },
    });
    fireEvent.change(screen.getByLabelText(/Offer or price/), { target: { value: '15' } });
    submit();

    await screen.findByText('Answer sent.');
    const [, options] = globalThis.fetch.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({
      kind: 'CAN_MAKE',
      message: 'I can knit you one',
      fee: '15',
    });
  });

  test('an empty message is refused locally — nothing leaves the page', async () => {
    globalThis.fetch = vi.fn();
    renderPage('know-where');

    submit();

    expect(await screen.findByText('Write a message.')).toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  test('an unknown answer kind bails out to home instead of posting garbage', async () => {
    globalThis.fetch = vi.fn();
    renderPage('not-a-kind');

    expect(await screen.findByText('HOME')).toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
