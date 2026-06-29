import { describe, test, expect } from 'vitest';
import { mapRow, validateRows, MAX_ROWS } from '../utils/bulkCsv';

describe('mapRow', () => {
  test('keeps known columns, trims them, and drops empty/whitespace cells', () => {
    const row = mapRow(
      { headline: '  Cazo  ', type: 'RENT_THING', fee: '5', description: '   ', location: 'BCN' },
      false
    );
    expect(row).toEqual({ headline: 'Cazo', type: 'RENT_THING', fee: '5', location: 'BCN' });
    expect(row).not.toHaveProperty('description'); // whitespace-only → dropped
  });

  test('ignores unknown columns', () => {
    const row = mapRow({ headline: 'X', evil: 'drop me', sku: '123' }, false);
    expect(row).toEqual({ headline: 'X' });
  });

  test('splits the tags cell on the pipe, trims and drops blanks', () => {
    const row = mapRow({ headline: 'X', tags: ' Cocina | Vintage |  | Metal ' }, false);
    expect(row.tags).toEqual(['Cocina', 'Vintage', 'Metal']);
  });

  test('omits tags when the cell is empty or whitespace', () => {
    expect(mapRow({ headline: 'X', tags: '   ' }, false)).not.toHaveProperty('tags');
    expect(mapRow({ headline: 'X' }, false)).not.toHaveProperty('tags');
  });

  test('keeps photo only when withPhoto is true (ZIP path)', () => {
    expect(mapRow({ headline: 'X', photo: 'cazo.jpg' }, true)).toMatchObject({ photo: 'cazo.jpg' });
    expect(mapRow({ headline: 'X', photo: 'cazo.jpg' }, false)).not.toHaveProperty('photo');
  });
});

describe('validateRows', () => {
  const rowsOf = (n, withHeadline = true) =>
    Array.from({ length: n }, (_, i) => (withHeadline ? { headline: `h${i}` } : { type: 'GIFT_THING' }));

  test('flags an empty set', () => {
    expect(validateRows([])).toBe('empty');
  });

  test('flags more than the max row count', () => {
    expect(validateRows(rowsOf(MAX_ROWS + 1))).toBe('tooMany');
  });

  test('accepts exactly the max row count', () => {
    expect(validateRows(rowsOf(MAX_ROWS))).toBeNull();
  });

  test('flags any row missing a headline', () => {
    expect(validateRows([{ headline: 'ok' }, { type: 'GIFT_THING' }])).toBe('headlineRequired');
  });

  test('passes when every row has a headline and bounds hold', () => {
    expect(validateRows(rowsOf(3))).toBeNull();
  });
});
