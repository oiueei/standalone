import { ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { hasPriceVerbs } from '../utils/collectionKind';

/**
 * The shared cluster of the Create and Edit collection forms that follows the mode:
 * for a stall or a library that members can add to, whether those members may set a
 * price, and under a "Visibility" heading the visibility toggle. Whether members may
 * recommend people is a setting of its own (the Notifications page), not asked here.
 *
 * What a collection holds is its kind, fixed when it is created, so there is no
 * longer a choice of verbs here. A COMMUNITY stall or library takes both of its
 * verbs when members may set a price (the default) and only the free one when
 * they may not; the page turns that switch into `allowed_thing_types`.
 *
 * Controlled: every value + setter is owned by the page; this component only
 * renders the cluster. `idPrefix` is `create-collection`
 * or `edit-collection`; `theeemeColor01` is the theeeme `color_01` token name.
 */
export default function CollectionForm({
  idPrefix,
  kind,
  mode = 'PROPRIETARY',
  visibility = 'PRIVATE',
  setVisibility = () => {},
  membersPrice = true,
  setMembersPrice = () => {},
  theeemeColor01,
}) {
  const { t } = useTranslation();
  const toggleTheme = theeemeColor01
    ? { '--toggle-button-color': `var(--color-${theeemeColor01})` }
    : undefined;
  // Only where members add things themselves and a price is possible at all.
  const showMembersPrice = hasPriceVerbs(kind) && mode === 'COMMUNITY';

  return (
    <>
      {showMembersPrice && (
        <ToggleButton
          id={`${idPrefix}-members-price`}
          variant="inline"
          label={t(
            kind === 'LIBRARY'
              ? 'collectionForm.membersPriceLibrary'
              : 'collectionForm.membersPriceStall'
          )}
          checked={membersPrice}
          onChange={(val) => setMembersPrice(!val)}
          theme={toggleTheme}
        />
      )}
      <h2 className="form-section-heading">{t('createCollection.visibilityHeading')}</h2>
      <ToggleButton
        id={`${idPrefix}-visibility`}
        variant="inline"
        label={t('visibility.publicFull')}
        checked={visibility === 'PUBLIC'}
        onChange={(val) => setVisibility(val ? 'PRIVATE' : 'PUBLIC')}
        theme={toggleTheme}
      />
    </>
  );
}
