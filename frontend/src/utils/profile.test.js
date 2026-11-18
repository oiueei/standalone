import { describe, it, expect } from 'vitest';
import { hasNoName, profileIncomplete } from './profile';

const FULL = { name: 'Lili', age_range: 'GEN_X', postal_code: '08038' };

describe('profileIncomplete', () => {
  it('is incomplete without a name, whatever else is filled in', () => {
    expect(profileIncomplete({ ...FULL, name: '' })).toBe(true);
    expect(profileIncomplete({ ...FULL, name: '   ' })).toBe(true);
  });

  it('is incomplete with a name but neither demographic field', () => {
    expect(profileIncomplete({ name: 'Lili', age_range: '', postal_code: '' })).toBe(true);
    expect(profileIncomplete({ name: 'Lili' })).toBe(true);
  });

  it('is complete with a name and either demographic field', () => {
    expect(profileIncomplete({ name: 'Lili', age_range: 'GEN_X', postal_code: '' })).toBe(false);
    expect(profileIncomplete({ name: 'Lili', age_range: '', postal_code: '08038' })).toBe(false);
  });

  it('is complete with everything filled in, and the language never counts', () => {
    expect(profileIncomplete(FULL)).toBe(false);
    expect(profileIncomplete({ ...FULL, language: '' })).toBe(false);
  });

  it('asks nothing of an account that has not been read', () => {
    expect(profileIncomplete(null)).toBe(false);
    expect(profileIncomplete(undefined)).toBe(false);
  });
});

describe('hasNoName', () => {
  it('is the name half of the rule', () => {
    expect(hasNoName({ name: '' })).toBe(true);
    expect(hasNoName({ name: ' ' })).toBe(true);
    expect(hasNoName({ name: 'Lili', age_range: '' })).toBe(false);
    expect(hasNoName(null)).toBe(true);
  });
});
