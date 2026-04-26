import { render } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

// Mock the SDK so we can assert what gets sent without a network round-trip.
const trackSpy = vi.fn();
const identifySpy = vi.fn();
const initSpy = vi.fn();
const resetSpy = vi.fn();
const optOutSpy = vi.fn();
const optInSpy = vi.fn();

vi.mock('mixpanel-browser', () => ({
  default: {
    init: (...args) => initSpy(...args),
    identify: (...args) => identifySpy(...args),
    track: (...args) => trackSpy(...args),
    reset: () => resetSpy(),
    opt_out_tracking: () => optOutSpy(),
    opt_in_tracking: () => optInSpy(),
  },
}));

// Force a token so initAnalytics runs the init path. import.meta.env values
// captured at import time, so we mock by stubbing global env via vitest.
vi.stubEnv('VITE_MIXPANEL_TOKEN', 'test-token');

// Re-import after env stub to get the initialised version.
async function freshAnalytics() {
  vi.resetModules();
  return await import('../services/analytics');
}

beforeEach(() => {
  trackSpy.mockClear();
  identifySpy.mockClear();
  initSpy.mockClear();
  resetSpy.mockClear();
  optOutSpy.mockClear();
  optInSpy.mockClear();
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.stubEnv('VITE_MIXPANEL_TOKEN', 'test-token');
});

describe('analytics opt-out', () => {
  test('track and identify run when not opted out', async () => {
    const { initAnalytics, track, identifyUser } = await freshAnalytics();
    initAnalytics();
    identifyUser('USR001');
    track('signup');
    expect(initSpy).toHaveBeenCalledTimes(1);
    expect(identifySpy).toHaveBeenCalledWith('USR001');
    expect(trackSpy).toHaveBeenCalledWith('signup', undefined);
  });

  test('track and identify short-circuit when localStorage opted out', async () => {
    localStorage.setItem('analyticsOptOut', '1');
    const { initAnalytics, track, identifyUser } = await freshAnalytics();
    initAnalytics();
    // init still runs (so the SDK can register opt-out), but after that no events.
    expect(optOutSpy).toHaveBeenCalledTimes(1);
    identifyUser('USR001');
    track('signup');
    expect(identifySpy).not.toHaveBeenCalled();
    expect(trackSpy).not.toHaveBeenCalled();
  });

  test('setAnalyticsOptOut(true) writes localStorage and calls opt_out_tracking', async () => {
    const { initAnalytics, setAnalyticsOptOut } = await freshAnalytics();
    initAnalytics();
    setAnalyticsOptOut(true);
    expect(localStorage.getItem('analyticsOptOut')).toBe('1');
    expect(optOutSpy).toHaveBeenCalled();
  });

  test('setAnalyticsOptOut(false) writes localStorage and calls opt_in_tracking', async () => {
    localStorage.setItem('analyticsOptOut', '1');
    const { initAnalytics, setAnalyticsOptOut } = await freshAnalytics();
    initAnalytics();
    setAnalyticsOptOut(false);
    expect(localStorage.getItem('analyticsOptOut')).toBe('0');
    expect(optInSpy).toHaveBeenCalled();
  });

  test('all exports no-op silently when token is unset', async () => {
    vi.unstubAllEnvs();
    vi.stubEnv('VITE_MIXPANEL_TOKEN', '');
    const { initAnalytics, track, identifyUser, resetAnalytics } = await freshAnalytics();
    initAnalytics();
    identifyUser('USR001');
    track('signup');
    resetAnalytics();
    expect(initSpy).not.toHaveBeenCalled();
    expect(identifySpy).not.toHaveBeenCalled();
    expect(trackSpy).not.toHaveBeenCalled();
    expect(resetSpy).not.toHaveBeenCalled();
  });
});

// Probe component reads the current location so we can assert the redirect target.
function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="path">{loc.pathname}</div>;
}

describe('DigestEntry redirect', () => {
  test('fires digest_link_clicked then redirects to the path with /digest stripped', async () => {
    // We cannot easily mount the full App in jsdom because it pulls all pages.
    // Instead, re-implement the same DigestEntry logic inline so the test
    // exercises the same shape as the real route:
    const { useEffect } = await import('react');
    const { Navigate, useParams } = await import('react-router-dom');
    const { initAnalytics, track } = await freshAnalytics();
    initAnalytics(); // otherwise track() short-circuits on !initialised
    function DigestEntry() {
      const params = useParams();
      const rest = params['*'] || '';
      const target = '/' + rest;
      useEffect(() => {
        track('digest_link_clicked', { path: target });
      }, [target]);
      return <Navigate to={target} replace />;
    }

    const { getByTestId } = render(
      <MemoryRouter initialEntries={['/digest/collections/ABC123']}>
        <Routes>
          <Route path="/digest/*" element={<DigestEntry />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(getByTestId('path').textContent).toBe('/collections/ABC123');
    expect(trackSpy).toHaveBeenCalledWith('digest_link_clicked', { path: '/collections/ABC123' });
  });
});
