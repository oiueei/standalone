import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Select } from 'hds-react';
import { WISH_KIND_SLUGS } from '../constants/things';

/**
 * "Contestar" dropdown for a wish card/detail (shown to non-owners).
 *
 * Like ShareCollectionMenu, HDS Select is hijacked as a one-shot action menu:
 * picking an option routes to the matching answer flow and the value resets.
 *  - "Tengo esto"      → publish a real listing (AddThingPage in respond mode),
 *                        which links it back as a HAVE_THIS response on save.
 *  - "Sé dónde"        → short form (RespondWishPage, kind=KNOW_WHERE).
 *  - "Puedo hacértelo" → short form (RespondWishPage, kind=CAN_MAKE).
 */
export default function RespondMenu({ thingCode, collectionCode, backPath, backLabel }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const options = [
    { value: 'HAVE_THIS', label: t('wishes.kind.haveThis') },
    { value: 'KNOW_WHERE', label: t('wishes.kind.knowWhere') },
    { value: 'CAN_MAKE', label: t('wishes.kind.canMake') },
  ];

  const go = (kind) => {
    if (kind === 'HAVE_THIS') {
      // Publishing a listing needs a collection context; a wish always has one,
      // but guard so we never route to /collections/undefined/add.
      if (!collectionCode) return;
      navigate(`/collections/${collectionCode}/add`, {
        state: { respondWishCode: thingCode, backPath, backLabel },
      });
      return;
    }
    const base = collectionCode
      ? `/collections/${collectionCode}/things/${thingCode}`
      : `/things/${thingCode}`;
    navigate(`${base}/respond/${WISH_KIND_SLUGS[kind]}`, { state: { backPath, backLabel } });
  };

  return (
    <Select
      language="en"
      id={`respond-${thingCode}`}
      texts={{ label: t('wishes.respond'), placeholder: t('wishes.respondPlaceholder') }}
      options={options}
      value={[]}
      onChange={(selected) => {
        const picked = selected && selected.length > 0 ? selected[0] : null;
        if (picked && picked.value) go(picked.value);
      }}
      visibleOptions={3}
    />
  );
}
