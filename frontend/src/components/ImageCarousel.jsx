import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { IconAngleLeft, IconAngleRight } from 'hds-react';
import { onImageError } from '../utils/imageFallback';

/**
 * Lightweight image carousel for a thing's photos ("Image pagination" in the DS).
 * Navigate with prev/next arrows (44px touch targets) or by swiping on touch.
 * Arrows disable at the first/last image (black-40 per DESIGN §11). Only rendered
 * when a thing has more than one photo. Things only.
 *
 * Props:
 *   images  – array of image URLs (cover first, then gallery)
 *   alt     – base alt text (the thing headline); each slide announces "{alt} — image X of N"
 *   variant – 'detail' (default, ThingPage) or 'card' (collection grid sizing)
 *   to      – optional route; when set the image links there (arrows stay separate
 *             so they only change the photo, never navigate)
 */
export default function ImageCarousel({ images = [], alt = '', variant = 'detail', to }) {
  const { t } = useTranslation();
  const [index, setIndex] = useState(0);
  const touchStartX = useRef(null);

  const count = images.length;
  if (count === 0) return null;

  const isCard = variant === 'card';
  const go = (delta) => setIndex((i) => Math.min(Math.max(i + delta, 0), count - 1));

  const onTouchStart = (e) => { touchStartX.current = e.touches[0].clientX; };
  const onTouchEnd = (e) => {
    if (touchStartX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
    touchStartX.current = null;
  };

  const announce = t('thingPage.galleryImageAlt', { name: alt, index: index + 1, total: count });
  const img = (
    <img
      className={isCard ? 'image-carousel-image image-carousel-image--card' : 'detail-image image-carousel-image'}
      src={images[index]}
      alt={announce}
      loading="lazy"
      onError={onImageError}
    />
  );

  return (
    <div
      className={`image-carousel${isCard ? ' image-carousel--card' : ''}`}
      role="group"
      aria-roledescription="carousel"
      aria-label={t('thingPage.galleryLabel')}
      onKeyDown={(e) => {
        if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); go(1); }
      }}
    >
      <span className="sr-only" aria-live="polite">{announce}</span>
      <div
        className={`image-carousel-viewport${isCard ? ' image-carousel-viewport--card' : ''}`}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {to ? <Link to={to}>{img}</Link> : img}
        <button
          type="button"
          className="image-carousel-arrow image-carousel-arrow--prev"
          onClick={() => go(-1)}
          disabled={index === 0}
          aria-label={t('thingPage.galleryPrev')}
        >
          <IconAngleLeft aria-hidden="true" />
        </button>
        <button
          type="button"
          className="image-carousel-arrow image-carousel-arrow--next"
          onClick={() => go(1)}
          disabled={index === count - 1}
          aria-label={t('thingPage.galleryNext')}
        >
          <IconAngleRight aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
