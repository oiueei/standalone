import mixpanel from 'mixpanel-browser';

const TOKEN = import.meta.env.VITE_MIXPANEL_TOKEN;
let initialised = false;

export function initAnalytics() {
  if (!TOKEN) return;
  try {
    mixpanel.init(TOKEN, { api_host: 'https://api-eu.mixpanel.com', persistence: 'localStorage' });
    initialised = true;
  } catch {
    // Mixpanel init failure must never crash the app
  }
}

export function identifyUser(userCode) {
  if (!initialised) return;
  try { mixpanel.identify(userCode); } catch { /* silent */ }
}

export function track(event, properties) {
  if (!initialised) return;
  try { mixpanel.track(event, properties); } catch { /* silent */ }
}

export function resetAnalytics() {
  if (!initialised) return;
  try { mixpanel.reset(); } catch { /* silent */ }
}
