import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import en from './locales/en.json';
import es from './locales/es.json';
import ca from './locales/ca.json';
import ptBR from './locales/pt-BR.json';
import ptPT from './locales/pt-PT.json';
import eu from './locales/eu.json';
import gl from './locales/gl.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    supportedLngs: ['en', 'es', 'ca', 'pt-BR', 'pt-PT', 'eu', 'gl'],
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
      'pt-BR': { translation: ptBR },
      'pt-PT': { translation: ptPT },
      eu: { translation: eu },
      gl: { translation: gl },
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
  { code: 'pt-BR', name: 'Português (Brasil)' },
  { code: 'pt-PT', name: 'Português (Portugal)' },
  { code: 'eu', name: 'Euskara' },
  { code: 'gl', name: 'Galego' },
];

export default i18n;
