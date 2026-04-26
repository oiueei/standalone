import mixpanel from 'mixpanel-browser';

const TOKEN = import.meta.env.VITE_MIXPANEL_TOKEN;
let initialised = false;

// Honour the user's opt-out (DESIGN.md §9 condition 4: visible opt-out).
// The flag is mirrored to localStorage by HomePage on each /auth/me/ fetch
// so we don't need to wait for a network round-trip on every track call.
function isOptedOut() {
  try { return localStorage.getItem('analyticsOptOut') === '1'; } catch { return false; }
}

export function initAnalytics() {
  if (!TOKEN) return;
  try {
    mixpanel.init(TOKEN, { api_host: 'https://api-eu.mixpanel.com', persistence: 'localStorage' });
    initialised = true;
    if (isOptedOut()) {
      try { mixpanel.opt_out_tracking(); } catch { /* silent */ }
    }
  } catch {
    // Mixpanel init failure must never crash the app
  }
}

export function identifyUser(userCode) {
  if (!initialised || isOptedOut()) return;
  try { mixpanel.identify(userCode); } catch { /* silent */ }
}

export function track(event, properties) {
  if (!initialised || isOptedOut()) return;
  try { mixpanel.track(event, properties); } catch { /* silent */ }
}

export function resetAnalytics() {
  if (!initialised) return;
  try { mixpanel.reset(); } catch { /* silent */ }
}

// Called when the user toggles opt-out in EditProfilePage. Mirrors to
// localStorage and instructs Mixpanel to stop sending immediately.
export function setAnalyticsOptOut(optedOut) {
  try { localStorage.setItem('analyticsOptOut', optedOut ? '1' : '0'); } catch { /* silent */ }
  if (!initialised) return;
  try {
    if (optedOut) mixpanel.opt_out_tracking();
    else mixpanel.opt_in_tracking();
  } catch { /* silent */ }
}
