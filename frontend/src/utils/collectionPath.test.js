import { describe, test, expect } from 'vitest';
import {
  COLLECTION_KINDS,
  COLLECTION_PREFIXES,
  collectionPath,
  collectionThingPath,
  isCodeShaped,
  kindOfPrefix,
  kindSegment,
} from './collectionPath';

describe('a collection lives at /{kind}/{code}', () => {
  test.each([
    ['STALL', '/stall/AbC123'],
    ['LIBRARY', '/library/AbC123'],
    ['SHED', '/shed/AbC123'],
  ])('%s → %s', (kind, path) => {
    expect(collectionPath('AbC123', kind)).toBe(path);
  });

  test.each([undefined, null, '', 'WISHLIST', 'stall'])(
    'without a known kind (%s) it is the address from before kinds',
    (kind) => {
      expect(collectionPath('AbC123', kind)).toBe('/collections/AbC123');
    }
  );

  test('a sub-page and a thing carry the rest of the path', () => {
    expect(collectionPath('AbC123', 'LIBRARY', '/edit')).toBe('/library/AbC123/edit');
    expect(collectionThingPath('AbC123', 'SHED', 'XyZ789')).toBe('/shed/AbC123/things/XyZ789');
    expect(collectionThingPath('AbC123', 'STALL', 'XyZ789', '/request')).toBe(
      '/stall/AbC123/things/XyZ789/request'
    );
  });

  test('every kind has its prefix, and the old one is kept beside them', () => {
    expect(COLLECTION_KINDS.map(kindSegment)).toEqual(['stall', 'library', 'shed']);
    expect(COLLECTION_PREFIXES).toEqual(['stall', 'library', 'shed', 'collections']);
  });

  test('a prefix names its kind, the old one names none', () => {
    expect(kindOfPrefix('library')).toBe('LIBRARY');
    expect(kindOfPrefix('collections')).toBeUndefined();
    expect(kindOfPrefix(undefined)).toBeUndefined();
  });
});

describe('isCodeShaped', () => {
  test.each(['ABC123', 'DELETE', '000000', 'USR001', 'L3L3oo', 'Delete', 'abc123'])(
    '%s has the shape of a code',
    (segment) => {
      expect(isCodeShaped(segment)).toBe(true);
    }
  );

  test.each(['ABC12', 'ABC1234', 'AB-123', 'foo', '', undefined, null])('%s has not', (segment) => {
    expect(isCodeShaped(segment)).toBe(false);
  });
});
