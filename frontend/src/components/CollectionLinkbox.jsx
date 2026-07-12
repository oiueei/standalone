import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Linkbox } from 'hds-react';

/**
 * A collection row (HDS Linkbox, no thumbnail) used in the collection grids
 * on HomePage (My / Inactive / Shared with me) and on a public profile
 * (collections in common). Clicking navigates client-side to the collection.
 * Deliberately image-less — thing cards keep their thumbnail, so a full-width
 * text-only row is what visually tells collections and things apart; a
 * collection's own thumbnail now lives on its `CollectionPage` hero instead
 * (`HeroPhoto`, see S7/S8).
 *
 * Props:
 *   collection – { code, headline, things?, invites? }
 *   showInfo   – show the "{N} things · {N} guests" line (the Home grids pass
 *                counts; the profile grid omits it). Requires things/invites.
 */
export default function CollectionLinkbox({ collection, showInfo = false }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <Linkbox
      href={`/collections/${collection.code}`}
      onClick={(e) => { e.preventDefault(); navigate(`/collections/${collection.code}`); }}
      heading={collection.headline}
      text={showInfo
        ? t('userPage.collectionInfo', { things: collection.things.length, guests: collection.invites.length })
        : undefined}
      linkAriaLabel={t('userPage.viewCollection', { headline: collection.headline })}
      linkboxAriaLabel={collection.headline}
      border
      size="small"
    />
  );
}
