import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import ContactPage from '../pages/ContactPage';
import CollaboratePage from '../pages/CollaboratePage';

// The support channel: public (a locked-out user is the main case), posts to
// /api/v1/contact/ and confirms receipt.

function mockResponse(body, ok = true, status = 200) {
  return { ok, status, json: () => Promise.resolve(body) };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/contact']}>
      <Routes>
        <Route path="/contact" element={<ContactPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ContactPage', () => {
  beforeEach(() => localStorage.clear());

  test('sends the message and confirms receipt', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({ message: 'ok' })));
    renderPage();
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'me@example.com' } });
    fireEvent.change(screen.getByLabelText(/Message/), { target: { value: 'Help!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText("We've got your message — we'll reply as soon as we can.")).toBeInTheDocument();
    const post = globalThis.fetch.mock.calls.find(([, o]) => o?.method === 'POST');
    expect(post[0]).toBe('/api/v1/contact/');
    expect(JSON.parse(post[1].body)).toMatchObject({ email: 'me@example.com', message: 'Help!', kind: 'support' });
  });

  test('the collaborate page shares the form but posts the collab kind', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({ message: 'ok' })));
    render(
      <MemoryRouter initialEntries={['/collaborate']}>
        <Routes>
          <Route path="/collaborate" element={<CollaboratePage />} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Collaborate with OIUEEI')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'dev@example.com' } });
    fireEvent.change(screen.getByLabelText(/Message/), { target: { value: 'I design.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText("We've got your message — we'll reply as soon as we can.")).toBeInTheDocument();
    const post = globalThis.fetch.mock.calls.find(([, o]) => o?.method === 'POST');
    expect(JSON.parse(post[1].body)).toMatchObject({ kind: 'collab' });
  });

  test('a rate limit shows the too-many-attempts message and keeps the form', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({}, false, 429)));
    renderPage();
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'me@example.com' } });
    fireEvent.change(screen.getByLabelText(/Message/), { target: { value: 'Help!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(
      await screen.findByText('Too many attempts — please wait a moment and try again.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument();
  });
});
