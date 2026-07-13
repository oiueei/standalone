import { describe, it, expect } from 'vitest';
import { parseLocalized, localizedText, localizedCounter } from './localized';

/**
 * The twin of core/tests/unit/test_localized.py. Both sides must agree on what
 * counts as a `{lang: text}` map: if the frontend were stricter, a card would
 * show raw braces for content the email renders as words (and vice versa).
 */

describe('parseLocalized', () => {
  it('reads a map of the languages OIUEEI speaks', () => {
    expect(parseLocalized('{"es": "Las cosas", "ca": "Les coses"}')).toEqual({
      es: 'Las cosas',
      ca: 'Les coses',
    });
  });

  it('accepts a single language', () => {
    expect(parseLocalized('{"ca": "Les coses"}')).toEqual({ ca: 'Les coses' });
  });

  it('tolerates surrounding whitespace', () => {
    expect(parseLocalized('  {"es": "Hola"}\n')).toEqual({ es: 'Hola' });
  });

  it.each([
    ['plain text', 'Las cosas de mamá'],
    ['empty', ''],
    ['broken json', '{not json}'],
    ['a list', '["es", "ca"]'],
    ['no language', '{}'],
    ['an unknown language', '{"es": "Hola", "fr": "Salut"}'],
    ['an empty translation', '{"es": ""}'],
    ['a non-string value', '{"es": 42}'],
    ['a non-string input', null],
  ])('leaves %s alone', (_label, value) => {
    expect(parseLocalized(value)).toBeNull();
  });
});

describe('localizedText', () => {
  const value = '{"es": "Las cosas", "ca": "Les coses", "en": "The things"}';

  it('returns plain text untouched', () => {
    expect(localizedText('Las cosas de mamá', 'ca')).toBe('Las cosas de mamá');
  });

  it('gives the reader their own language', () => {
    expect(localizedText(value, 'ca')).toBe('Les coses');
    expect(localizedText(value, 'en')).toBe('The things');
  });

  it('accepts a full i18n tag', () => {
    expect(localizedText(value, 'en-GB')).toBe('The things');
  });

  it('falls back to Spanish when the owner skipped the reader’s language', () => {
    expect(localizedText('{"es": "Las cosas", "ca": "Les coses"}', 'en')).toBe('Las cosas');
  });

  it('falls back to the first language written when there is no Spanish', () => {
    expect(localizedText('{"ca": "Les coses", "en": "The things"}', 'fr')).toBe('Les coses');
  });

  it('never shows raw braces to anyone', () => {
    expect(localizedText('{"ca": "Les coses"}', undefined)).toBe('Les coses');
  });
});

describe('localizedCounter', () => {
  it('counts plain text as it always did', () => {
    expect(localizedCounter('hola', 64)).toEqual({ text: '4/64', over: false });
  });

  it('flags plain text over the limit', () => {
    expect(localizedCounter('a'.repeat(65), 64).over).toBe(true);
  });

  it('counts a map per language — each one gets the whole limit', () => {
    const counter = localizedCounter('{"es": "hola", "ca": "ei"}', 64);
    expect(counter.text).toBe('es 4/64 · ca 2/64');
    expect(counter.over).toBe(false);
  });

  it('flags the map when one language overflows', () => {
    expect(localizedCounter(`{"es": "hola", "ca": "${'a'.repeat(65)}"}`, 64).over).toBe(true);
  });

  it('treats an empty value as zero', () => {
    expect(localizedCounter('', 64)).toEqual({ text: '0/64', over: false });
  });
});
