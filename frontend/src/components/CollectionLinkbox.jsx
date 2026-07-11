import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Linkbox } from 'hds-react';

/**
 * A collection card (HDS Linkbox) used in the collection grids on HomePage
 * (My / Inactive / Shared with me) and on a public profile (collections in
 * common). Clicking navigates client-side to the collection; the thumbnail is
 * optional.
 *
 * Props:
 *   collection – { code, headline, thumbnail_url, things?, invites? }
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
      imgProps={collection.thumbnail_url ? { src: collection.thumbnail_url, alt: collection.headline } : undefined}
      border
      size="small"
    />
  );
}
