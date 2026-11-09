import { renderHook, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import en from '../i18n/locales/en.json';

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../services/api';
import useShareLink from './useShareLink';

const ok = (data) => Promise.resolve({ ok: true, status: 200, json: async () => data });

describe('useShareLink', () => {
  let writeText;

  beforeEach(() => {
    vi.clearAllMocks();
    writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  });

  test('two copies of a private group’s link are one request', async () => {
    apiFetch.mockImplementation(() => ok({ share_url: 'https://x.test/share/T' }));
    const { result } = renderHook(() =>
      useShareLink({ code: 'COL001', kind: 'LIBRARY', isPublic: false })
    );

    await act(() => result.current.copy());
    await act(() => result.current.copy());

    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch.mock.calls[0][0]).toBe('/api/v1/collections/COL001/share-link/');
    expect(writeText).toHaveBeenCalledTimes(2);
    expect(writeText).toHaveBeenCalledWith('https://x.test/share/T');
    expect(result.current.toast).toEqual({ type: 'success', message: en.shareMenu.copied });
  });

  test('a public group’s link is its own address, with no request', async () => {
    const { result } = renderHook(() =>
      useShareLink({ code: 'COL001', kind: 'SHED', isPublic: true })
    );

    await act(() => result.current.copy());

    expect(apiFetch).not.toHaveBeenCalled();
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/shed/COL001`);
  });

  test('a refused request says linkError and copies nothing', async () => {
    apiFetch.mockImplementation(() => Promise.resolve({ ok: false, status: 403 }));
    const { result } = renderHook(() =>
      useShareLink({ code: 'COL001', kind: 'LIBRARY', isPublic: false })
    );

    await act(() => result.current.copy());

    expect(writeText).not.toHaveBeenCalled();
    expect(result.current.toast).toEqual({ type: 'error', message: en.shareMenu.linkError });
  });

  test('a clipboard that refuses says copyError', async () => {
    writeText.mockImplementation(() => Promise.reject(new Error('denied')));
    const { result } = renderHook(() =>
      useShareLink({ code: 'COL001', kind: 'STALL', isPublic: true })
    );

    await act(() => result.current.copy());

    expect(result.current.toast).toEqual({ type: 'error', message: en.shareMenu.copyError });
  });

  test('a link set by the caller is the one kept, and null forgets it', async () => {
    apiFetch.mockImplementation(() => ok({ share_url: 'https://x.test/share/NEW' }));
    const { result } = renderHook(() =>
      useShareLink({ code: 'COL001', kind: 'LIBRARY', isPublic: false })
    );

    act(() => result.current.setUrl('https://x.test/share/ROTATED'));
    await act(() => result.current.copy());
    expect(apiFetch).not.toHaveBeenCalled();
    expect(writeText).toHaveBeenCalledWith('https://x.test/share/ROTATED');

    act(() => result.current.setUrl(null));
    await act(() => result.current.copy());
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenLastCalledWith('https://x.test/share/NEW');
  });
});
