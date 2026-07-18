import { describe, test, expect } from 'vitest';
import es from './es';
import ca from './ca';
import en from './en';

// The legal text is per-language content, not i18n keys — this is its parity
// guard (the analogue of i18nParity for src/legal/): every language must ship
// the same section structure, so no reader gets a shorter truth than another.
describe('legal content parity', () => {
  const contents = { es, ca, en };

  test('every language ships substantial content', () => {
    for (const [lang, text] of Object.entries(contents)) {
      expect(text.length, lang).toBeGreaterThan(1000);
    }
  });

  test('every language has the same number of sections', () => {
    const sections = (text) => text.split('\n').filter((l) => l.startsWith('# ')).length;
    expect(sections(es)).toBeGreaterThanOrEqual(5);
    expect(sections(ca)).toBe(sections(es));
    expect(sections(en)).toBe(sections(es));
  });
});
