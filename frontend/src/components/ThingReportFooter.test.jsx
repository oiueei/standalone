import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, afterEach } from 'vitest';
import ThingReportFooter from './ThingReportFooter';

// The trigger carries aria-expanded; the confirm button inside the panel does
// not — that distinction keeps the two same-labelled "Report" buttons apart.
const openConfirm = () => {
  fireEvent.click(screen.getByRole('button', { name: 'Report', expanded: false }));
};
const confirmButton = () =>
  screen.getAllByRole('button', { name: 'Report' }).find((b) => !b.hasAttribute('aria-expanded'));

describe('ThingReportFooter (the anonymous report flow)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('opening the confirm states the anonymity promise and sends nothing yet', () => {
    globalThis.fetch = vi.fn();
    render(<ThingReportFooter thingCode="THG001" onToast={vi.fn()} />);

    openConfirm();

    // The reporter is told the owner never learns who reported — BEFORE sending.
    expect(screen.getByText(/they won't see who/)).toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  test('cancelling closes the confirm without reporting anything', () => {
    globalThis.fetch = vi.fn();
    render(<ThingReportFooter thingCode="THG001" onToast={vi.fn()} />);

    openConfirm();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByText('Report this listing?')).not.toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  test('confirming POSTs the report and thanks the reporter', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ status: 'reported' }),
    });
    const onToast = vi.fn();
    render(<ThingReportFooter thingCode="THG001" onToast={onToast} />);

    openConfirm();
    fireEvent.click(confirmButton());

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({
        type: 'success',
        message: "Thanks — we've let the owner know.",
      })
    );
    const [url, options] = globalThis.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/things/THG001/report/');
    expect(options.method).toBe('POST');
    // The confirm collapses once the report is in.
    expect(screen.queryByText('Report this listing?')).not.toBeInTheDocument();
  });

  test('a rate-limited report says "wait", not "broken"', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ detail: 'Request was throttled.' }),
    });
    const onToast = vi.fn();
    render(<ThingReportFooter thingCode="THG001" onToast={onToast} />);

    openConfirm();
    fireEvent.click(confirmButton());

    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith({
        type: 'error',
        message: 'Too many attempts — please wait a moment and try again.',
      })
    );
  });
});
