import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import en from './locales/en.json';

// English (the fallback language) ships in the main bundle so the very first
// paint is always translated — no key ever flashes and English users fetch
// nothing extra. Spanish and Catalan are ~40 kB each and were bundled eagerly
// too; instead pull them in on demand as their own Vite chunks via this tiny
// i18next backend, so only the active language's file is ever downloaded. A
// Spanish/Catalan visitor sees English for the moment before their chunk lands
// (fallback already in memory), then it swaps in — no spinner, no blank.
const lazyLocaleBackend = {
  type: 'backend',
  init() {},
  read(language, namespace, callback) {
    // en is already in `resources` below, so i18next only asks the backend for
    // the on-demand languages. The template import lets Vite code-split each
    // locale JSON into its own chunk.
    import(`./locales/${language}.json`)
      .then((mod) => callback(null, mod.default))
      .catch((err) => callback(err, false));
  },
};

i18n
  .use(lazyLocaleBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    // Retired locales (pt-BR, pt-PT, eu, gl) fall back to es rather than the
    // global default en — closer to the original translation, kept dormant
    // (not deleted) in case they're reinstated. `pt` covers a bare navigator
    // language of "pt" as well as the "pt-*" variants.
    fallbackLng: {
      'pt-BR': ['es'],
      'pt-PT': ['es'],
      pt: ['es'],
      eu: ['es'],
      gl: ['es'],
      default: ['en'],
    },
    supportedLngs: ['en', 'es', 'ca'],
    // Load only the base code (es, not es-ES) so the backend never reaches for a
    // region chunk that doesn't exist.
    load: 'currentOnly',
    // en is bundled while es/ca come from the backend — mixing the two needs
    // this flag so i18next doesn't treat the bundled set as exhaustive.
    partialBundledLanguages: true,
    detection: {
      // Honour a saved choice first, then the browser language; persist the
      // user's pick so it survives reloads and overrides the browser default.
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
    resources: {
      en: { translation: en },
    },
    // The fallback (en) is always in memory, so render what we have and swap the
    // active language in when its chunk arrives rather than suspending. Avoids a
    // Suspense-fallback that would itself need translations (LoadingSpinner does).
    react: { useSuspense: false },
    interpolation: { escapeValue: false },
  });

// Language names shown in their own language (endonyms) for the in-app picker.
// Order and codes mirror supportedLngs above. Deliberately not i18n keys — a
// language is always listed in its own language, so these never get translated.
export const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Español' },
  { code: 'ca', name: 'Català' },
];

export default i18n;
