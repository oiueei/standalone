import { describe, test, expect } from 'vitest';
import { onImageError } from './imageFallback';

describe('onImageError', () => {
  test('swaps a broken image to the placeholder', () => {
    const img = document.createElement('img');
    img.src = 'https://res.cloudinary.com/demo/gone.jpg';

    onImageError({ currentTarget: img });

    expect(img.src).toContain('image-m');
    expect(img.dataset.fallback).toBe('1');
  });

  // The guard is the point: a placeholder that itself fails would otherwise
  // re-enter this handler and reset src forever.
  test('a second error on an already-swapped image changes nothing', () => {
    const img = document.createElement('img');
    img.src = 'https://res.cloudinary.com/demo/gone.jpg';

    onImageError({ currentTarget: img });
    const swapped = img.src;
    onImageError({ currentTarget: img });

    expect(img.src).toBe(swapped);
  });
});
