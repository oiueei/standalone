import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { IconSpeechbubbleText } from 'hds-react';

/**
 * The support channel's entrance (i8): a quiet speech-bubble link at the
 * hero's top-right, beside the logo watermark, on every page. Rendered INSIDE
 * `.form-hero-content` (so `--hero-text-color` resolves — the icon must stay
 * visible on dark theeemes, same rationale as the hero back link) but
 * absolutely positioned against `.form-hero`. 44px touch target.
 */
export default function ContactCorner() {
  const { t } = useTranslation();
  return (
    <Link
      to="/contact"
      className="contact-corner"
      aria-label={t('contact.linkLabel')}
      title={t('contact.linkLabel')}
    >
      <IconSpeechbubbleText aria-hidden="true" />
    </Link>
  );
}
