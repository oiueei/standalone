import { describe, it, expect } from 'vitest';
import { phoneHref } from './phone';

describe('phoneHref', () => {
  it('keeps only digits and the plus sign', () => {
    expect(phoneHref('+34 (600) 123-456')).toBe('+34600123456');
    expect(phoneHref('93.123 45 67')).toBe('931234567');
  });

  it('gives an empty string for nothing', () => {
    expect(phoneHref('')).toBe('');
    expect(phoneHref(null)).toBe('');
    expect(phoneHref(undefined)).toBe('');
  });
});
