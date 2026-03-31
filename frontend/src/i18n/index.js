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
      order: ['navigator'],
      caches: [],
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

export default i18n;
