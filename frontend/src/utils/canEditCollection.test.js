import { describe, test, expect } from 'vitest';
import { canEditCollection } from './canEditCollection';

describe('canEditCollection', () => {
  test.each([
    ['no collection', null, 'ABC123', false],
    ['a member', { is_curator: false, mode: 'COMMUNITY', owner: 'OWN001' }, 'ABC123', false],
    [
      'a curator of a proprietary group',
      { is_curator: true, mode: 'PROPRIETARY', owner: 'OWN001' },
      'ABC123',
      true,
    ],
    [
      'a curator of a community group',
      { is_curator: true, mode: 'COMMUNITY', owner: 'OWN001' },
      'ABC123',
      true,
    ],
    [
      'the founder of a network',
      { is_curator: true, mode: 'NETWORK', owner: 'ABC123' },
      'ABC123',
      true,
    ],
    [
      'a co-curator of a network',
      { is_curator: true, mode: 'NETWORK', owner: 'OWN001' },
      'ABC123',
      false,
    ],
    [
      'a network and nobody signed in',
      { is_curator: true, mode: 'NETWORK', owner: 'OWN001' },
      null,
      false,
    ],
    [
      'a member of a network, even its founder code',
      { is_curator: false, mode: 'NETWORK', owner: 'ABC123' },
      'ABC123',
      false,
    ],
  ])('%s', (_name, collection, userCode, expected) => {
    expect(canEditCollection(collection, userCode)).toBe(expected);
  });
});
