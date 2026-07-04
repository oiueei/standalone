import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import en from './locales/en.json';
import es from './locales/es.json';
import ca from './locales/ca.json';

i18n
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
    detection: {
      // Honour a saved choice first, then the browser language; persist the
      // user's pick so it survives reloads and overrides the browser default.
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
    resources: {
      en: { translation: en },
      es: { translation: es },
      ca: { translation: ca },
    },
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
