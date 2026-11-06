import { describe, test, expect } from 'vitest';
import { withQuantity } from './quantity';

// A stand-in for `t` that shows the key and what it was given.
const t = (key, options) => `${key}:${options.count}:${options.headline}`;

describe('withQuantity', () => {
  test('a request for several names the thing with how many', () => {
    expect(withQuantity(t, 'Arduino kit', 4)).toBe('common.quantityTimes:4:Arduino kit');
  });

  test('the quantity may come as text', () => {
    expect(withQuantity(t, 'Arduino kit', '3')).toBe('common.quantityTimes:3:Arduino kit');
  });

  test.each([[1], [0], [undefined], [null], ['x'], [-2]])(
    'with %j it is the name as it was',
    (quantity) => {
      expect(withQuantity(t, 'Arduino kit', quantity)).toBe('Arduino kit');
    }
  );
});
