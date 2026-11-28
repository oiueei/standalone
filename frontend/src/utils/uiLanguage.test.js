import { describe, test, expect } from 'vitest';
import { uiLanguage } from './uiLanguage';

describe('uiLanguage', () => {
  test('a regional tag counts as its language', () => {
    expect(uiLanguage({ language: 'es-ES' })).toBe('es');
  });

  test('the code is lower case', () => {
    expect(uiLanguage({ language: 'CA' })).toBe('ca');
  });

  test.each([[{ language: '' }], [{ language: undefined }], [{}], [undefined], [null]])(
    'no language on screen gives an empty string (%j)',
    (i18n) => {
      expect(uiLanguage(i18n)).toBe('');
    }
  );

  test('it follows `language` even when `resolvedLanguage` stays on the fallback', () => {
    expect(uiLanguage({ language: 'ca', resolvedLanguage: 'en' })).toBe('ca');
  });
});
