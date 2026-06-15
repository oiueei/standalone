import placeholder from '../assets/image-m.png';

/**
 * `onError` handler for `<img>`: swap a broken image to the OIUEEI placeholder.
 *
 * Guards with a `data-fallback` flag so a failing placeholder can't trigger an
 * infinite error loop. Pair with `loading="lazy"` on the same image.
 */
export function onImageError(e) {
  const img = e.currentTarget;
  if (img.dataset.fallback) return;
  img.dataset.fallback = '1';
  img.src = placeholder;
}
